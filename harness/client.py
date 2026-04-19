from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any, Awaitable, Callable

from harness.agents.loop import AsyncAgentLoop, LoopSettings, OpenAIChatCompletionsClient
from harness.agents.prompt import build_system_instructions
from harness.config.settings import HarnessConfig, load_harness_config
from harness.models.types import AgentRunResult
from harness.sandbox.runtime import BasicSandbox
from harness.skills import Skill, load_skills
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry


logger = logging.getLogger(__name__)


def resolve_project_root(start_path: Path) -> Path:
    """Resolve repository root by walking upward from a starting path."""
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

        sandbox = BasicSandbox(
            self.config.sandbox.root_dir,
            command_timeout_seconds=self.config.sandbox.command_timeout_seconds,
            max_output_chars=self.config.runtime.max_output_chars,
        )
        self._sandbox_root = self.config.sandbox.root_dir
        registry = ToolRegistry.with_default_tools(sandbox)
        self._tool_executor = ToolExecutor(registry)
        self._tool_schemas = registry.list_tool_schemas()

    def _load_enabled_skills(self, *, sync_to_sandbox: bool = True) -> list[Skill]:
        skills_path = self._project_root / "skills"
        extensions_config_path = str(self._project_root / "extensions_config.json")
        skills = load_skills(
            skills_path=skills_path,
            enabled_only=True,
            extensions_config_path=extensions_config_path,
        )
        if sync_to_sandbox:
            self._sync_skills_into_sandbox(skills)
        return skills

    def list_enabled_skill_names(self) -> list[str]:
        return [item.name for item in self._load_enabled_skills(sync_to_sandbox=False)]

    def _sync_skills_into_sandbox(self, skills: list[Skill]) -> None:
        for item in skills:
            target_path = self._sandbox_root / item.get_container_file_path("skills")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(item.skill_file, target_path)
            except OSError as exc:
                logger.warning("Failed to copy skill %s into sandbox: %s", item.name, exc)

    def _build_agent(
        self,
        model_name: str | None = None,
        *,
        pinned_skills: list[str] | None = None,
        compact_summary: str | None = None,
    ) -> AsyncAgentLoop:
        selected_model = self.config.get_model(model_name)
        skills = self._load_enabled_skills()

        model_client = OpenAIChatCompletionsClient(
            api_key=selected_model.read_api_key(),
            base_url=selected_model.base_url,
        )

        return AsyncAgentLoop(
            model_client=model_client,
            tool_executor=self._tool_executor,
            tool_schemas=self._tool_schemas,
            settings=LoopSettings(
                model=selected_model.model,
                max_steps=self.config.runtime.max_steps,
                temperature=selected_model.temperature,
                max_tokens=selected_model.max_tokens,
            ),
            instructions=build_system_instructions(
                skills,
                container_base_path="skills",
                pinned_skills=pinned_skills,
                compact_summary=compact_summary,
            ),
        )

    def list_models(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for model in self.config.models:
            items.append(
                {
                    "name": model.name,
                    "display_name": model.display_name,
                    "provider": model.provider,
                    "supports_vision": model.supports_vision,
                    "default": model.name == self.config.default_model,
                }
            )
        return items

    async def run_async(
        self,
        prompt: str,
        model_name: str | None = None,
        *,
        on_text_delta: Callable[[str], Awaitable[None] | None] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        pinned_skills: list[str] | None = None,
        compact_summary: str | None = None,
    ) -> AgentRunResult:
        agent = self._build_agent(
            model_name,
            pinned_skills=pinned_skills,
            compact_summary=compact_summary,
        )
        if on_text_delta is None:
            return await agent.run(prompt, history_messages=conversation_history)
        return await agent.run_with_stream(
            prompt,
            on_text_delta=on_text_delta,
            history_messages=conversation_history,
        )

    def run(self, prompt: str, model_name: str | None = None) -> AgentRunResult:
        return asyncio.run(self.run_async(prompt, model_name))

