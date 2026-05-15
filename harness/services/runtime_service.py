from __future__ import annotations

import os
from pathlib import Path

from harness.config.settings import HarnessConfig
from harness.context import ThreadRuntimePaths
from harness.memory import format_memory_for_injection, get_memory_data
from harness.models.types import RuntimeContext
from harness.rag import KnowledgeBaseService
from harness.sandbox.runtime import BasicSandbox
from harness.tools.reminder import ReminderScheduler


class HarnessRuntimeService:
    def __init__(
        self,
        *,
        config: HarnessConfig,
        sandbox_root: Path,
        reminders: ReminderScheduler,
    ) -> None:
        self.config = config
        self.sandbox_root = sandbox_root
        self.reminders = reminders
        self._knowledge_base: KnowledgeBaseService | None = None

    def get_knowledge_base(self) -> KnowledgeBaseService:
        if self._knowledge_base is None:
            self._knowledge_base = KnowledgeBaseService(self.config.rag)
        return self._knowledge_base

    def make_runtime_context(
        self,
        *,
        selected_model_name: str,
        thread_paths: ThreadRuntimePaths | None,
        thread_id: str | None,
        subagent_depth: int,
        knowledge_base: KnowledgeBaseService | None = None,
    ) -> RuntimeContext:
        return RuntimeContext(
            thread_id=thread_id,
            thread_root=thread_paths.thread_root if thread_paths else self.sandbox_root,
            workspace_dir=thread_paths.workspace_dir if thread_paths else self.sandbox_root,
            model_name=selected_model_name,
            subagent_depth=subagent_depth,
            max_subagents=self.config.runtime.max_concurrent_subagents,
            subagent_timeout_seconds=self.config.runtime.subagent_timeout_seconds,
            knowledge_base=knowledge_base,
            reminders=self.reminders,
        )

    def make_sandbox(self, thread_paths: ThreadRuntimePaths | None) -> BasicSandbox:
        if thread_paths is None:
            return BasicSandbox(
                self.sandbox_root,
                command_timeout_seconds=self.config.sandbox.command_timeout_seconds,
                max_output_chars=self.config.runtime.max_output_chars,
            )
        return BasicSandbox(
            thread_paths.thread_root,
            command_cwd=thread_paths.workspace_dir,
            allowed_roots=[thread_paths.shared_skills_dir],
            command_timeout_seconds=self.config.sandbox.command_timeout_seconds,
            max_output_chars=self.config.runtime.max_output_chars,
        )

    def build_memory_text(self, current_user_message: str) -> str:
        if not self.config.memory.enabled or not self.config.memory.injection_enabled:
            return ""
        memory_data = get_memory_data(self.config)
        return format_memory_for_injection(
            memory_data,
            current_user_message,
            max_tokens=self.config.memory.max_injection_tokens,
        )

    def get_shared_skills_root(self, thread_paths: ThreadRuntimePaths | None) -> Path:
        if thread_paths is not None:
            return thread_paths.shared_skills_dir
        return self.sandbox_root / "users" / "local" / "skills"

    def skill_dir_is_current(self, source_dir: Path, target_dir: Path) -> bool:
        source_marker = source_dir / "SKILL.md"
        target_marker = target_dir / "SKILL.md"
        if not target_marker.exists():
            return False
        return self.directory_mtime_ns(target_dir) >= self.directory_mtime_ns(source_dir) and target_marker.stat().st_size == source_marker.stat().st_size

    def directory_mtime_ns(self, directory: Path) -> int:
        latest = 0
        for current_root, dir_names, file_names in os.walk(directory):
            dir_names[:] = [name for name in dir_names if not name.startswith(".")]
            current_path = Path(current_root)
            latest = max(latest, current_path.stat().st_mtime_ns)
            for file_name in file_names:
                file_path = current_path / file_name
                latest = max(latest, file_path.stat().st_mtime_ns)
        return latest
