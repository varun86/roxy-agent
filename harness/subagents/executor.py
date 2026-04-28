from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Awaitable, Callable


MAX_CONCURRENT_SUBAGENTS = 3


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SubagentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(slots=True)
class SubagentResult:
    task_id: str
    status: SubagentStatus
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress_messages: list[str] = field(default_factory=list)


_background_tasks: dict[str, SubagentResult] = {}
_background_tasks_lock = threading.Lock()
_scheduler_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SUBAGENTS, thread_name_prefix="subagent-scheduler-")
_execution_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SUBAGENTS, thread_name_prefix="subagent-exec-")


class SubagentExecutor:
    def __init__(
        self,
        *,
        task_id: str,
        timeout_seconds: int,
        run_callable: Callable[[SubagentResult], Awaitable[str]],
    ) -> None:
        self.task_id = task_id
        self.timeout_seconds = timeout_seconds
        self._run_callable = run_callable

    async def _aexecute(self, result_holder: SubagentResult | None = None) -> SubagentResult:
        result = result_holder or SubagentResult(task_id=self.task_id, status=SubagentStatus.RUNNING, started_at=_utc_now())
        try:
            final_text = await self._run_callable(result)
            result.status = SubagentStatus.COMPLETED
            result.result = final_text
            result.completed_at = _utc_now()
        except Exception as exc:
            result.status = SubagentStatus.FAILED
            result.error = str(exc)
            result.completed_at = _utc_now()
        return result

    def execute(self, result_holder: SubagentResult | None = None) -> SubagentResult:
        try:
            return asyncio.run(self._aexecute(result_holder))
        except Exception as exc:
            result = result_holder or SubagentResult(task_id=self.task_id, status=SubagentStatus.FAILED)
            result.status = SubagentStatus.FAILED
            result.error = str(exc)
            result.completed_at = _utc_now()
            return result

    def execute_async(self) -> str:
        result = SubagentResult(task_id=self.task_id, status=SubagentStatus.PENDING)
        with _background_tasks_lock:
            _background_tasks[self.task_id] = result

        def run_task() -> None:
            with _background_tasks_lock:
                current = _background_tasks[self.task_id]
                current.status = SubagentStatus.RUNNING
                current.started_at = _utc_now()
                result_holder = current
            try:
                execution_future: Future[SubagentResult] = _execution_pool.submit(self.execute, result_holder)
                try:
                    exec_result = execution_future.result(timeout=self.timeout_seconds)
                    with _background_tasks_lock:
                        current = _background_tasks[self.task_id]
                        current.status = exec_result.status
                        current.result = exec_result.result
                        current.error = exec_result.error
                        current.completed_at = exec_result.completed_at or _utc_now()
                        current.progress_messages = list(exec_result.progress_messages)
                except FuturesTimeoutError:
                    execution_future.cancel()
                    with _background_tasks_lock:
                        current = _background_tasks[self.task_id]
                        current.status = SubagentStatus.TIMED_OUT
                        current.error = f"Execution timed out after {self.timeout_seconds} seconds"
                        current.completed_at = _utc_now()
            except Exception as exc:
                with _background_tasks_lock:
                    current = _background_tasks[self.task_id]
                    current.status = SubagentStatus.FAILED
                    current.error = str(exc)
                    current.completed_at = _utc_now()

        _scheduler_pool.submit(run_task)
        return self.task_id


def get_background_task_result(task_id: str) -> SubagentResult | None:
    with _background_tasks_lock:
        return _background_tasks.get(task_id)


def cleanup_background_task(task_id: str) -> None:
    with _background_tasks_lock:
        result = _background_tasks.get(task_id)
        if result is None:
            return
        if result.status in {SubagentStatus.COMPLETED, SubagentStatus.FAILED, SubagentStatus.TIMED_OUT}:
            del _background_tasks[task_id]
