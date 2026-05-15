from __future__ import annotations

import asyncio

from harness.models.types import ToolCall, ToolResult
from harness.tools.registry import ToolRegistry, ToolRuntime


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, runtime: ToolRuntime) -> None:
        self.registry = registry
        self.runtime = runtime

    async def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        handler = self.registry.get_handler(tool_call.name)
        if handler is None:
            result = ToolResult(
                call_id=tool_call.id,
                output=f"Unknown tool: {tool_call.name}",
                is_error=True,
            )
            await self._emit_tool_called(tool_call, result)
            return result

        try:
            output = await handler(self.runtime, tool_call.arguments)
            result = ToolResult(call_id=tool_call.id, output=output, is_error=False)
        except Exception as exc:  # pragma: no cover - defensive layer
            result = ToolResult(
                call_id=tool_call.id,
                output=f"Tool execution error ({tool_call.name}): {type(exc).__name__}: {exc}",
                is_error=True,
            )
        await self._emit_tool_called(tool_call, result)
        return result

    async def execute_batch(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        return list(await asyncio.gather(*(self.execute_tool_call(call) for call in tool_calls)))

    async def _emit_tool_called(self, tool_call: ToolCall, result: ToolResult) -> None:
        if self.runtime.emit_event is None:
            return
        maybe = self.runtime.emit_event(
            {
                "type": "tool_called",
                "call_id": tool_call.id,
                "tool_name": tool_call.name,
                "arguments": tool_call.arguments,
                "output": result.output,
                "is_error": result.is_error,
            }
        )
        if maybe is not None:
            await maybe
