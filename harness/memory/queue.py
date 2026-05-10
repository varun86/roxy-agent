from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging

from harness.config.settings import HarnessConfig
from harness.memory.updater import MemoryUpdater

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConversationContext:
    thread_id: str
    messages: list[dict[str, str]]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class MemoryUpdateQueue:
    def __init__(self, config: HarnessConfig):
        self._config = config
        self._queue: list[ConversationContext] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._processing = False

    def add(self, *, thread_id: str, messages: list[dict[str, str]]) -> None:
        if not self._config.memory.enabled:
            logger.debug("Skipping memory queue add: memory disabled")
            return
        context = ConversationContext(thread_id=thread_id, messages=messages)
        with self._lock:
            self._queue = [item for item in self._queue if item.thread_id != thread_id]
            self._queue.append(context)
            self._reset_timer()
        logger.debug("Queued memory update for thread %s", thread_id)

    def _reset_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._config.memory.debounce_seconds, self._process_queue)
        self._timer.daemon = True
        self._timer.start()

    def _process_queue(self) -> None:
        with self._lock:
            if self._processing:
                self._reset_timer()
                return
            if not self._queue:
                return
            self._processing = True
            contexts = self._queue.copy()
            self._queue.clear()
            self._timer = None

        try:
            updater = MemoryUpdater(self._config)
            for index, context in enumerate(contexts):
                try:
                    updated = updater.update_memory(context.messages, thread_id=context.thread_id)
                    if not updated:
                        logger.warning("Memory update returned false for thread %s", context.thread_id)
                except Exception as exc:
                    logger.exception("Memory update failed for thread %s: %s", context.thread_id, exc)
                if index + 1 < len(contexts):
                    time.sleep(0.1)
        finally:
            with self._lock:
                self._processing = False

    def flush(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self._process_queue()

    def clear(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._queue.clear()
            self._processing = False


_queues: dict[int, MemoryUpdateQueue] = {}
_queue_lock = threading.Lock()


def get_memory_queue(config: HarnessConfig) -> MemoryUpdateQueue:
    key = id(config)
    with _queue_lock:
        queue = _queues.get(key)
        if queue is None:
            queue = MemoryUpdateQueue(config)
            _queues[key] = queue
        return queue


def reset_memory_queues() -> None:
    with _queue_lock:
        for queue in _queues.values():
            queue.clear()
        _queues.clear()
