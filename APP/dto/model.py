from __future__ import annotations

from pydantic import BaseModel


class ModelInfo(BaseModel):
    name: str
    display_name: str
    provider: str
    supports_vision: bool
    default: bool
