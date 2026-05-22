from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PluginStatusResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    plugin_id: str
    enabled: bool
    service_running: bool = False
    last_error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class PluginActionRequest(BaseModel):
    text: str | None = None
    payload: dict[str, Any] | None = None
