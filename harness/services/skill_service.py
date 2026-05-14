from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from harness.context import ThreadRuntimePaths
from harness.services.runtime_service import HarnessRuntimeService
from harness.skills import Skill, load_skills


class SkillService:
    def __init__(
        self,
        *,
        project_root: Path,
        runtime_service: HarnessRuntimeService,
    ) -> None:
        self._project_root = project_root
        self._runtime_service = runtime_service
        self._skills_cache_key: tuple[Any, ...] | None = None
        self._skills_cache_value: list[Skill] | None = None

    def load_enabled_skills(
        self,
        *,
        sync_to_sandbox: bool = True,
        thread_paths: ThreadRuntimePaths | None = None,
    ) -> list[Skill]:
        skills_path = self._project_root / "skills"
        extensions_config_path = str(self._project_root / "extensions_config.json")
        cache_key = self._build_skills_cache_key(skills_path, Path(extensions_config_path))
        if self._skills_cache_key == cache_key and self._skills_cache_value is not None:
            skills = self._skills_cache_value
        else:
            skills = load_skills(
                skills_path=skills_path,
                enabled_only=True,
                extensions_config_path=extensions_config_path,
            )
            self._skills_cache_key = cache_key
            self._skills_cache_value = skills
        if sync_to_sandbox:
            self._sync_skills_into_sandbox(skills, thread_paths=thread_paths)
        return skills

    def list_enabled_skill_names(self) -> list[str]:
        return [item.name for item in self.load_enabled_skills(sync_to_sandbox=False)]

    def _sync_skills_into_sandbox(
        self,
        skills: list[Skill],
        *,
        thread_paths: ThreadRuntimePaths | None = None,
    ) -> None:
        sandbox_root = self._runtime_service.get_shared_skills_root(thread_paths)
        for item in skills:
            target_dir = sandbox_root / item.category / item.skill_path if item.skill_path else sandbox_root / item.category
            if self._runtime_service.skill_dir_is_current(item.skill_dir, target_dir):
                continue
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(item.skill_dir, target_dir, dirs_exist_ok=True)

    def _build_skills_cache_key(self, skills_path: Path, extensions_config_path: Path) -> tuple[Any, ...]:
        root = skills_path.resolve()
        config = extensions_config_path.resolve()
        snapshot: list[tuple[str, int, int]] = []
        for category in ("public", "custom"):
            category_path = root / category
            if not category_path.exists():
                continue
            for current_root, dir_names, file_names in os.walk(category_path):
                dir_names[:] = sorted(name for name in dir_names if not name.startswith("."))
                if "SKILL.md" not in file_names:
                    continue
                skill_file = Path(current_root) / "SKILL.md"
                stat = skill_file.stat()
                snapshot.append((str(skill_file.relative_to(root)), stat.st_mtime_ns, stat.st_size))

        config_snapshot = None
        if config.exists():
            stat = config.stat()
            config_snapshot = (stat.st_mtime_ns, stat.st_size)
        return str(root), tuple(snapshot), config_snapshot
