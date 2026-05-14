from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from harness.config.settings import HarnessConfig
from harness.context import ThreadRuntimePaths
from harness.models.types import AgentRunResult
from harness.subagents import (
    SubagentExecutor,
    SubagentResult,
    SubagentStatus,
    cleanup_background_task,
    get_background_task_result,
    get_subagent_config,
)


class SubagentService:
    def __init__(self, *, config: HarnessConfig) -> None:
        self._config = config

    async def run_subagent(
        self,
        *,
        build_agent: Callable[..., Any],
        selected_model_name: str,
        thread_paths: ThreadRuntimePaths | None,
        thread_id: str | None,
        emit_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None,
        description: str,
        prompt: str,
        subagent_type: str,
        max_steps: int | None,
    ) -> str:
        config = get_subagent_config(subagent_type)
        if config is None:
            raise RuntimeError(f"Unknown subagent type: {subagent_type}")

        task_id = f"task_{uuid.uuid4().hex[:8]}"
        effective_steps = max_steps or config.max_steps

        async def emit(payload: dict[str, Any]) -> None:
            if emit_event is None:
                return
            maybe = emit_event(payload)
            if maybe is not None:
                await maybe

        async def run_callable(result_holder: SubagentResult) -> str:
            progress_messages: list[str] = []

            async def on_delta(delta: str) -> None:
                if delta:
                    progress_messages.append(delta)
                    await emit({"type": "task_running", "task_id": task_id, "message": delta})

            agent = build_agent(
                selected_model_name,
                thread_paths=thread_paths,
                subagent_depth=1,
                instructions_override=config.system_prompt,
                tool_allowlist=config.tools,
                tool_denylist=config.disallowed_tools,
                max_steps_override=effective_steps,
                subagent_enabled=False,
                event_callback=emit_event,
                thread_id=thread_id,
            )
            result: AgentRunResult = await agent.run_with_stream(prompt, on_text_delta=on_delta)
            if result.text.strip():
                return result.text
            return "".join(progress_messages).strip()

        executor = SubagentExecutor(
            task_id=task_id,
            timeout_seconds=config.timeout_seconds or self._config.runtime.subagent_timeout_seconds,
            run_callable=run_callable,
        )

        await emit(
            {
                "type": "task_started",
                "task_id": task_id,
                "description": description,
                "subagent_type": subagent_type,
            }
        )
        executor.execute_async()

        while True:
            result = get_background_task_result(task_id)
            if result is None:
                await asyncio.sleep(0.1)
                continue
            if result.status == SubagentStatus.COMPLETED:
                await emit({"type": "task_completed", "task_id": task_id, "result": result.result or ""})
                cleanup_background_task(task_id)
                return f"Task Succeeded. Result: {result.result or '(empty response)'}"
            if result.status == SubagentStatus.FAILED:
                await emit({"type": "task_failed", "task_id": task_id, "error": result.error or "unknown error"})
                cleanup_background_task(task_id)
                raise RuntimeError(result.error or "Subagent failed")
            if result.status == SubagentStatus.TIMED_OUT:
                await emit({"type": "task_timed_out", "task_id": task_id, "error": result.error or "timed out"})
                cleanup_background_task(task_id)
                raise RuntimeError(result.error or "Subagent timed out")
            await asyncio.sleep(0.1)
