from __future__ import annotations

from typing import Any

from harness.client import HarnessClient


class ModelService:
    def __init__(self, client: HarnessClient) -> None:
        self._client = client

    def list_models(self) -> list[dict[str, Any]]:
        return self._client.list_models()
