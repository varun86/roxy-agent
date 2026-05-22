from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol


@dataclass(slots=True)
class PluginStatus:
    plugin_id: str = ""
    enabled: bool = False
    service_running: bool = False
    last_error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
            "service_running": self.service_running,
            "last_error": self.last_error,
            "details": dict(self.details),
        }
        payload.update(self.details)
        return payload


@dataclass(frozen=True, slots=True)
class PluginHostContext:
    project_root: Path
    config_path: Path
    plugin_root: Path
    enabled: bool
    config: dict[str, Any]
    fallback_tts_line_generator: Callable[[str], Awaitable[str]] | None = None


class PluginBase(Protocol):
    plugin_id: str

    @property
    def plugin_name(self) -> str:
        ...

    @property
    def plugin_version(self) -> str:
        ...

    @property
    def priority(self) -> int:
        ...

    def initialize(self, register: Any, host: PluginHostContext) -> None:
        ...

    def shutdown(self) -> None:
        ...
