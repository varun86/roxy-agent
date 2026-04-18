from __future__ import annotations

import asyncio
from typing import AsyncIterator

from harness.client import HarnessClient
from harness.models.types import AgentRunResult


class ChatService:
    def __init__(self, client: HarnessClient | None = None) -> None:
        self._client = client or HarnessClient()

    async def run_chat(self, message: str, model: str | None = None) -> AgentRunResult:
        return await self._client.run_async(message, model)

    async def run_chat_stream(self, message: str, model: str | None = None) -> AsyncIterator[dict[str, object]]:
        yield {"type": "start"}

        queue: asyncio.Queue[str] = asyncio.Queue()

        async def on_text_delta(delta: str) -> None:
            await queue.put(delta)

        task = asyncio.create_task(self._client.run_async(message, model, on_text_delta=on_text_delta))

        while True:
            if task.done() and queue.empty():
                break

            try:
                delta = await asyncio.wait_for(queue.get(), timeout=0.05)
                yield {"type": "delta", "delta": delta}
            except TimeoutError:
                continue

        result = await task

        yield {
            "type": "done",
            "text": result.text,
            "trace": {
                "steps": result.trace.steps,
                "tool_calls": result.trace.tool_calls,
                "errors": result.trace.errors,
            },
        }

    def list_models(self) -> list[dict[str, object]]:
        return self._client.list_models()


_service: ChatService | None = None


def get_chat_service() -> ChatService:
    global _service
    if _service is None:
        _service = ChatService()
    return _service
