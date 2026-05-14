from __future__ import annotations

import asyncio
import atexit
import concurrent.futures

from harness.config.extensions_config import ExtensionsConfig
from harness.mcp.tools import McpToolAdapter, get_mcp_tool_adapters

_cached_tools: list[McpToolAdapter] | None = None
_cached_key: tuple[str | None, int | None, int | None] | None = None
_MCP_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="mcp-cache")

atexit.register(lambda: _MCP_EXECUTOR.shutdown(wait=False))


def get_cached_mcp_tools(config_path: str | None = None) -> list[McpToolAdapter]:
    global _cached_key, _cached_tools
    key = _build_cache_key(config_path)
    if _cached_tools is not None and _cached_key == key:
        return _cached_tools
    _cached_tools = _run_loader(config_path)
    _cached_key = key
    return _cached_tools


def reset_mcp_tools_cache() -> None:
    global _cached_key, _cached_tools
    _cached_key = None
    _cached_tools = None


def _build_cache_key(config_path: str | None) -> tuple[str | None, int | None, int | None]:
    resolved = ExtensionsConfig.resolve_config_path(config_path)
    if resolved is None:
        return None, None, None
    stat = resolved.stat()
    return str(resolved), stat.st_mtime_ns, stat.st_size


def _run_loader(config_path: str | None) -> list[McpToolAdapter]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        future = _MCP_EXECUTOR.submit(asyncio.run, get_mcp_tool_adapters(config_path))
        return future.result()
    return asyncio.run(get_mcp_tool_adapters(config_path))
