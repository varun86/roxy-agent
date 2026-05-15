from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from harness.config.settings import HarnessConfig, load_harness_config
from harness.context import ThreadRuntimePaths
from harness.services import (
    AgentService,
    HarnessRuntimeService,
    McpService,
    ModelService,
    SkillService,
    SubagentService,
)
from harness.tools.reminder import ReminderScheduler


def resolve_project_root(start_path: Path) -> Path:
    current = start_path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "harness").is_dir():
            return candidate
    return current


class HarnessClient:
    def __init__(self, config: HarnessConfig | None = None, *, project_root: Path | None = None) -> None:
        self._project_root = resolve_project_root(project_root or Path.cwd())
        self.config = config or load_harness_config(self._project_root)
        self._sandbox_root = self.config.sandbox.root_dir
        self._reminders = ReminderScheduler(self.config.sandbox.root_dir / "reminders.json")

        self._runtime_service = HarnessRuntimeService(
            config=self.config,
            sandbox_root=self._sandbox_root,
            reminders=self._reminders,
        )
        self._skill_service = SkillService(
            project_root=self._project_root,
            runtime_service=self._runtime_service,
        )
        self._mcp_service = McpService(project_root=self._project_root)
        self._model_service = ModelService(config=self.config)
        self._subagent_service = SubagentService(config=self.config)
        self._agent_service = AgentService(
            config=self.config,
            runtime_service=self._runtime_service,
            skill_service=self._skill_service,
            mcp_service=self._mcp_service,
            run_subagent=self._run_subagent,
        )

    @property
    def reminders(self) -> ReminderScheduler:
        return self._reminders

    def list_enabled_skill_names(self) -> list[str]:
        return self._skill_service.list_enabled_skill_names()

    def get_mcp_config(self) -> dict[str, dict[str, Any]]:
        return self._mcp_service.get_mcp_config()

    def update_mcp_config(self, mcp_servers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return self._mcp_service.update_mcp_config(mcp_servers)

    def list_models(self) -> list[dict[str, Any]]:
        return self._model_service.list_models()

    def _load_enabled_skills(
        self,
        *,
        sync_to_sandbox: bool = True,
        thread_paths: ThreadRuntimePaths | None = None,
    ):
        return self._skill_service.load_enabled_skills(sync_to_sandbox=sync_to_sandbox, thread_paths=thread_paths)

    def _make_sandbox(self, thread_paths: ThreadRuntimePaths | None):
        return self._runtime_service.make_sandbox(thread_paths)

    def _build_agent(
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
    ):
        return self._agent_service.build_agent(
            model_name,
            thread_paths=thread_paths,
            pinned_skills=pinned_skills,
            compact_summary=compact_summary,
            subagent_depth=subagent_depth,
            instructions_override=instructions_override,
            tool_allowlist=tool_allowlist,
            tool_denylist=tool_denylist,
            max_steps_override=max_steps_override,
            subagent_enabled=subagent_enabled,
            event_callback=event_callback,
            thread_id=thread_id,
            current_user_message=current_user_message,
        )

    async def _run_subagent(
        self,
        *,
        selected_model_name: str,
        thread_paths: ThreadRuntimePaths | None,
        thread_id: str | None,
        emit_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None,
        description: str,
        prompt: str,
        subagent_type: str,
        max_steps: int | None,
    ) -> str:
        return await self._subagent_service.run_subagent(
            build_agent=self._agent_service.build_agent,
            selected_model_name=selected_model_name,
            thread_paths=thread_paths,
            thread_id=thread_id,
            emit_event=emit_event,
            description=description,
            prompt=prompt,
            subagent_type=subagent_type,
            max_steps=max_steps,
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
    ):
        return await self._agent_service.run_async(
            prompt,
            model_name,
            on_text_delta=on_text_delta,
            conversation_history=conversation_history,
            thread_id=thread_id,
            thread_paths=thread_paths,
            pinned_skills=pinned_skills,
            compact_summary=compact_summary,
            event_callback=event_callback,
        )

    def run(self, prompt: str, model_name: str | None = None):
        return self._agent_service.run(prompt, model_name)
