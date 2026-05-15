from __future__ import annotations

from typing import Any

from harness.client import HarnessClient


class McpService:
    def __init__(self, client: HarnessClient) -> None:
        self._client = client

    def get_mcp_config(self) -> dict[str, dict[str, Any]]:
        return self._client.get_mcp_config()

    def update_mcp_config(self, mcp_servers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return self._client.update_mcp_config(mcp_servers)
