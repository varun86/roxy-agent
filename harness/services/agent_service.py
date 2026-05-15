from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from harness.agents.loop import AsyncAgentLoop, LoopSettings, OpenAIChatCompletionsClient
from harness.agents.prompt import build_system_instructions
from harness.config.settings import HarnessConfig
from harness.context import ThreadRuntimePaths
from harness.services.mcp_service import McpService
from harness.services.runtime_service import HarnessRuntimeService
from harness.services.skill_service import SkillService
from harness.tools.executor import ToolExecutor
from harness.tools.local_browser import LocalBrowserClient
from harness.tools.registry import ToolRegistry, ToolRuntime
from harness.models.types import AgentRunResult


class AgentService:
    def __init__(
        self,
        *,
        config: HarnessConfig,
        runtime_service: HarnessRuntimeService,
        skill_service: SkillService,
        mcp_service: McpService,
        run_subagent: Callable[..., Awaitable[str]],
    ) -> None:
        self._config = config
        self._runtime_service = runtime_service
        self._skill_service = skill_service
        self._mcp_service = mcp_service
        self._run_subagent = run_subagent

    def build_agent(
        self,
        model_name: str | None = None,
        *,
        thread_paths: ThreadRuntimePaths | None = None,
        pinned_skills: list[str] | None = None,
        compact_summary: str | None = None,
        subagent_depth: int = 0,
        instructions_override: str | None = None,
        tool_allowlist: list[str] | None = None,
        tool_denylist: list[str] | None = None,
        max_steps_override: int | None = None,
        subagent_enabled: bool | None = None,
        event_callback: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
        thread_id: str | None = None,
        current_user_message: str = "",
    ) -> AsyncAgentLoop:
        selected_model = self._config.get_model(model_name)
        sandbox = self._runtime_service.make_sandbox(thread_paths)
        knowledge_base = self._runtime_service.get_knowledge_base()
        effective_subagent_enabled = self._config.runtime.subagents_enabled if subagent_enabled is None else subagent_enabled
        include_task_tool = effective_subagent_enabled and subagent_depth == 0
        mcp_tools = self._mcp_service.get_runtime_tools()
        local_browser_enabled = self._config.local_browser.enabled and not self._mcp_service.is_server_enabled("playwright")
        registry = ToolRegistry.with_default_tools(
            sandbox,
            local_browser_client=LocalBrowserClient(
                enabled=local_browser_enabled,
                search_engine_template=self._config.local_browser.search_engine,
                allowed_domains=self._config.local_browser.allowed_domains,
            ),
            local_browser_enabled=local_browser_enabled,
            knowledge_base=knowledge_base,
            include_task_tool=include_task_tool,
            extra_tools=mcp_tools,
        )
        if tool_allowlist is not None or tool_denylist is not None:
            registry = registry.filtered(allowlist=tool_allowlist, denylist=tool_denylist)

        runtime_context = self._runtime_service.make_runtime_context(
            selected_model_name=selected_model.name,
            thread_paths=thread_paths,
            thread_id=thread_id,
            subagent_depth=subagent_depth,
            knowledge_base=knowledge_base,
        )

        runtime = ToolRuntime(
            sandbox=sandbox,
            context=runtime_context,
            emit_event=event_callback,
            run_subagent=(
                None
                if not include_task_tool
                else lambda description, prompt, subagent_type, max_steps: self._run_subagent(
                    selected_model_name=selected_model.name,
                    thread_paths=thread_paths,
                    thread_id=thread_id,
                    emit_event=event_callback,
                    description=description,
                    prompt=prompt,
                    subagent_type=subagent_type,
                    max_steps=max_steps,
                )
            ),
        )
        tool_executor = ToolExecutor(registry, runtime)
        tool_schemas = registry.list_tool_schemas()
        skills = self._skill_service.load_enabled_skills(thread_paths=thread_paths)
        model_client = OpenAIChatCompletionsClient(
            api_key=selected_model.read_api_key(),
            base_url=selected_model.base_url,
        )

        instructions = instructions_override or build_system_instructions(
            skills,
            container_base_path="skills",
            pinned_skills=pinned_skills,
            compact_summary=compact_summary,
            memory_text=self._runtime_service.build_memory_text(current_user_message),
            subagent_enabled=include_task_tool,
            max_concurrent_subagents=self._config.runtime.max_concurrent_subagents,
        )

        return AsyncAgentLoop(
            model_client=model_client,
            tool_executor=tool_executor,
            tool_schemas=tool_schemas,
            settings=LoopSettings(
                model=selected_model.model,
                max_steps=max_steps_override or self._config.runtime.max_steps,
                temperature=selected_model.temperature,
                max_tokens=selected_model.max_tokens,
            ),
            instructions=instructions,
            max_concurrent_subagents=self._config.runtime.max_concurrent_subagents,
        )

    async def run_async(
        self,
        prompt: str,
        model_name: str | None = None,
        *,
        on_text_delta: Callable[[str], Awaitable[None] | None] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        thread_id: str | None = None,
        thread_paths: ThreadRuntimePaths | None = None,
        pinned_skills: list[str] | None = None,
        compact_summary: str | None = None,
        event_callback: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ) -> AgentRunResult:
        agent = self.build_agent(
            model_name,
            thread_paths=thread_paths,
            pinned_skills=pinned_skills,
            compact_summary=compact_summary,
            event_callback=event_callback,
            thread_id=thread_id,
            current_user_message=prompt,
        )
        return await agent.run_with_stream(
            prompt,
            history_messages=conversation_history,
            on_text_delta=on_text_delta,
        )

    def run(self, prompt: str, model_name: str | None = None) -> AgentRunResult:
        import asyncio

        return asyncio.run(self.run_async(prompt, model_name))
