from __future__ import annotations

import pytest

from harness.agents.loop import AsyncAgentLoop, ChatCompletionsModelClient, LoopSettings
from harness.models.types import RuntimeContext, ToolCall
from harness.sandbox.runtime import BasicSandbox
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry, ToolRuntime


class TooManyTasksClient(ChatCompletionsModelClient):
    def __init__(self) -> None:
        self.calls = 0

    async def create_response(self, *, model, messages, tools, temperature=None, max_tokens=None, on_delta=None):
        self.calls += 1
        if self.calls == 1:
            return (
                "",
                [
                    ToolCall(id="1", name="task", arguments={"description": "a", "prompt": "a", "subagent_type": "general-purpose"}),
                    ToolCall(id="2", name="task", arguments={"description": "b", "prompt": "b", "subagent_type": "general-purpose"}),
                    ToolCall(id="3", name="task", arguments={"description": "c", "prompt": "c", "subagent_type": "general-purpose"}),
                    ToolCall(id="4", name="task", arguments={"description": "d", "prompt": "d", "subagent_type": "general-purpose"}),
                ],
            )
        return ("done", [])


@pytest.mark.asyncio
async def test_loop_truncates_excess_subagent_calls(tmp_path):
    sandbox = BasicSandbox(tmp_path)
    registry = ToolRegistry.with_default_tools(sandbox, include_task_tool=True)
    executor = ToolExecutor(
        registry,
        ToolRuntime(
            sandbox=sandbox,
            context=RuntimeContext(),
            run_subagent=lambda description, prompt, subagent_type, max_steps: __import__("asyncio").sleep(0, result="ok"),
        ),
    )
    loop = AsyncAgentLoop(
        model_client=TooManyTasksClient(),
        tool_executor=executor,
        tool_schemas=registry.list_tool_schemas(),
        settings=LoopSettings(model="fake", max_steps=2),
        instructions="test",
        max_concurrent_subagents=3,
    )

    result = await loop.run("go")

    assert result.text == "done"
    assert result.trace.tool_calls == 3
    assert result.trace.subagent_calls == 3
    assert result.trace.subagent_errors == 1
