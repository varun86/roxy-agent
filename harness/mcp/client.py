from __future__ import annotations

from typing import Any

from harness.config.extensions_config import ExtensionsConfig, McpServerConfig


def build_server_params(server_name: str, config: McpServerConfig) -> dict[str, Any]:
    transport = config.type or "stdio"
    params: dict[str, Any] = {"transport": transport}

    if transport == "stdio":
        if not config.command:
            raise ValueError(f"MCP server '{server_name}' with stdio transport requires command")
        params["command"] = config.command
        params["args"] = list(config.args)
        if config.env:
            params["env"] = dict(config.env)
        return params

    if transport in ("http", "sse"):
        if not config.url:
            raise ValueError(f"MCP server '{server_name}' with {transport} transport requires url")
        params["url"] = config.url
        if config.headers:
            params["headers"] = dict(config.headers)
        return params

    raise ValueError(f"MCP server '{server_name}' has unsupported transport type: {transport}")


def build_servers_config(extensions_config: ExtensionsConfig) -> dict[str, dict[str, Any]]:
    servers: dict[str, dict[str, Any]] = {}
    for name, server in extensions_config.get_enabled_mcp_servers().items():
        servers[name] = build_server_params(name, server)
    return servers
