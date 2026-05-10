from __future__ import annotations

import abc
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness.config.settings import HarnessConfig


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def create_empty_memory() -> dict[str, Any]:
    return {
        "version": "1.0",
        "lastUpdated": utc_now_iso(),
        "user": {
            "workContext": {"summary": "", "updatedAt": ""},
            "personalContext": {"summary": "", "updatedAt": ""},
            "topOfMind": {"summary": "", "updatedAt": ""},
        },
        "history": {
            "recentMonths": {"summary": "", "updatedAt": ""},
            "earlierContext": {"summary": "", "updatedAt": ""},
            "longTermBackground": {"summary": "", "updatedAt": ""},
        },
        "facts": [],
    }


class MemoryStorage(abc.ABC):
    @abc.abstractmethod
    def load(self) -> dict[str, Any]: ...

    @abc.abstractmethod
    def reload(self) -> dict[str, Any]: ...

    @abc.abstractmethod
    def save(self, memory_data: dict[str, Any]) -> bool: ...


class FileMemoryStorage(MemoryStorage):
    def __init__(self, file_path: Path):
        self._file_path = file_path
        self._cache: tuple[dict[str, Any], float | None] | None = None

    def _load_from_file(self) -> dict[str, Any]:
        if not self._file_path.exists():
            return create_empty_memory()
        try:
            with self._file_path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return create_empty_memory()
        return data if isinstance(data, dict) else create_empty_memory()

    def load(self) -> dict[str, Any]:
        try:
            current_mtime = self._file_path.stat().st_mtime if self._file_path.exists() else None
        except OSError:
            current_mtime = None

        if self._cache is None or self._cache[1] != current_mtime:
            data = self._load_from_file()
            self._cache = (data, current_mtime)
            return data
        return self._cache[0]

    def reload(self) -> dict[str, Any]:
        data = self._load_from_file()
        try:
            current_mtime = self._file_path.stat().st_mtime if self._file_path.exists() else None
        except OSError:
            current_mtime = None
        self._cache = (data, current_mtime)
        return data

    def save(self, memory_data: dict[str, Any]) -> bool:
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            memory_data["lastUpdated"] = utc_now_iso()
            temp_path = self._file_path.with_suffix(self._file_path.suffix + ".tmp")
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(memory_data, handle, ensure_ascii=False, indent=2)
            temp_path.replace(self._file_path)
            try:
                current_mtime = self._file_path.stat().st_mtime
            except OSError:
                current_mtime = None
            self._cache = (memory_data, current_mtime)
            return True
        except OSError:
            return False


_storage_instances: dict[str, MemoryStorage] = {}
_storage_lock = threading.Lock()


def get_memory_storage(config: HarnessConfig) -> MemoryStorage:
    key = str(config.memory.storage_path)
    with _storage_lock:
        storage = _storage_instances.get(key)
        if storage is None:
            storage = FileMemoryStorage(config.memory.storage_path)
            _storage_instances[key] = storage
        return storage


def reset_memory_storage() -> None:
    with _storage_lock:
        _storage_instances.clear()
