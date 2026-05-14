from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.config.extensions_config import ExtensionsConfig, McpServerConfig, reload_extensions_config
from harness.mcp import get_cached_mcp_tools, reset_mcp_tools_cache
from harness.mcp.tools import McpToolAdapter


class McpService:
    def __init__(self, *, project_root: Path) -> None:
        self._project_root = project_root

    @property
    def config_path(self) -> Path:
        return self._project_root / "extensions_config.json"

    def get_mcp_config(self) -> dict[str, dict[str, Any]]:
        config = ExtensionsConfig.from_file(str(self.config_path))
        return {"mcp_servers": {name: server.to_dict() for name, server in config.mcp_servers.items()}}

    def update_mcp_config(self, mcp_servers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        current = ExtensionsConfig.from_file(str(self.config_path))
        updated = ExtensionsConfig(
            mcp_servers={name: McpServerConfig.from_dict(value) for name, value in mcp_servers.items()},
            skills=current.skills,
        )
        with self.config_path.open("w", encoding="utf-8") as handle:
            json.dump(updated.to_dict(), handle, ensure_ascii=False, indent=2)
        reload_extensions_config(str(self.config_path))
        reset_mcp_tools_cache()
        return {"mcp_servers": {name: server.to_dict() for name, server in updated.mcp_servers.items()}}

    def get_runtime_tools(self) -> list[McpToolAdapter]:
        return get_cached_mcp_tools(str(self.config_path))
