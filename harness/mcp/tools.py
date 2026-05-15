from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from harness.config.extensions_config import ExtensionsConfig
from harness.mcp.client import build_servers_config
from harness.tools.registry import ToolHandler, ToolRuntime, ToolSpec

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class McpToolAdapter:
    spec: ToolSpec
    handler: ToolHandler


async def get_mcp_tool_adapters(config_path: str | None = None) -> list[McpToolAdapter]:
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("langchain-mcp-adapters not installed; MCP tools disabled")
        return []

    extensions_config = ExtensionsConfig.from_file(config_path)
    servers_config = build_servers_config(extensions_config)
    if not servers_config:
        return []

    client = MultiServerMCPClient(servers_config, tool_name_prefix=True)
    tools = await client.get_tools()

    adapters: list[McpToolAdapter] = []
    for tool in tools:
        spec = ToolSpec(
            name=str(getattr(tool, "name", "")),
            description=str(getattr(tool, "description", "") or "MCP tool"),
            parameters=_tool_parameters(tool),
        )
        adapters.append(McpToolAdapter(spec=spec, handler=_build_handler(tool)))
    return adapters


def _tool_parameters(tool: Any) -> dict[str, Any]:
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is None:
        return {"type": "object", "properties": {}}
    if hasattr(args_schema, "model_json_schema"):
        return args_schema.model_json_schema()
    if hasattr(args_schema, "schema"):
        return args_schema.schema()
    return {"type": "object", "properties": {}}


def _build_handler(tool: Any) -> ToolHandler:
    async def handler(runtime: ToolRuntime, args: dict[str, Any]) -> str:
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke(args)
        elif hasattr(tool, "invoke"):
            result = await asyncio.to_thread(tool.invoke, args)
        else:
            raise RuntimeError(f"MCP tool '{getattr(tool, 'name', 'unknown')}' cannot be invoked")
        return _stringify_result(result)

    return handler


def _stringify_result(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
