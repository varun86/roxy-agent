from __future__ import annotations

import asyncio
import shutil
from typing import Any, Callable

from harness.client import HarnessClient
from harness.context import (
    ConversationStore,
    ConversationTrace,
    ThreadContextStore,
    ThreadRuntimeResolver,
    ToolCallEvent,
    generate_thread_id,
)
from harness.models.types import AgentRunResult


class AppRuntimeService:
    def __init__(
        self,
        client: HarnessClient,
        *,
        memory_queue_getter: Callable[[Any], Any],
    ) -> None:
        self.client = client
        self._memory_queue_getter = memory_queue_getter
        runtime = self.client.config.runtime
        self.context_store = ThreadContextStore(
            max_recent_messages=runtime.max_recent_messages,
            compact_threshold_chars=runtime.compact_threshold_chars,
            skill_memory_max=runtime.skill_memory_max,
        )
        self.conversation_store = ConversationStore()
        self.thread_runtime = ThreadRuntimeResolver(self.client.config.sandbox.root_dir)
        self.thread_locks: dict[str, asyncio.Lock] = {}

    def normalize_thread_id(self, thread_id: str | None = None) -> str | None:
        if thread_id and thread_id.strip():
            return thread_id.strip()
        return None

    def resolve_or_create_thread_id(self, thread_id: str | None = None) -> str:
        return self.normalize_thread_id(thread_id) or generate_thread_id()

    def get_thread_lock(self, thread_id: str) -> asyncio.Lock:
        lock = self.thread_locks.get(thread_id)
        if lock is None:
            lock = asyncio.Lock()
            self.thread_locks[thread_id] = lock
        return lock

    def build_history(
        self,
        resolved_thread_id: str,
        *,
        messages: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        thread_paths = self.thread_runtime.ensure_dirs(self.thread_runtime.resolve(resolved_thread_id))
        detail = self.conversation_store.load_conversation(
            resolved_thread_id,
            conversation_path=thread_paths.conversation_file,
            messages_path=thread_paths.messages_file,
        )
        conversation_history = self.conversation_store.build_history_messages(
            detail,
            max_messages=self.client.config.runtime.max_recent_messages,
        )
        if conversation_history:
            return conversation_history

        context = self.context_store.load(resolved_thread_id, context_path=thread_paths.context_file)
        return self.context_store.build_history(context, messages)

    def queue_memory_update(
        self,
        *,
        thread_id: str,
        user_message: str,
        assistant_message: str,
        history: list[dict[str, str]],
    ) -> None:
        payload = [*history, {"role": "user", "content": user_message}, {"role": "assistant", "content": assistant_message}]
        try:
            queue = self._memory_queue_getter(self.client.config)
            queue.add(thread_id=thread_id, messages=payload)
        except Exception:
            return

    @staticmethod
    def build_trace_info(result: AgentRunResult) -> ConversationTrace:
        return ConversationTrace(
            steps=result.trace.steps,
            tool_calls=result.trace.tool_calls,
            errors=result.trace.errors,
            subagent_calls=result.trace.subagent_calls,
            subagent_errors=result.trace.subagent_errors,
        )

    @staticmethod
    def build_tool_event(event: dict[str, object]) -> ToolCallEvent | None:
        if event.get("type") != "tool_called":
            return None
        call_id = event.get("call_id")
        tool_name = event.get("tool_name")
        arguments = event.get("arguments")
        output = event.get("output")
        if not isinstance(call_id, str) or not call_id:
            return None
        if not isinstance(tool_name, str) or not tool_name:
            return None
        return ToolCallEvent(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments if isinstance(arguments, dict) else {},
            output=output if isinstance(output, str) else "",
            is_error=bool(event.get("is_error")),
        )

    def delete_thread_root(self, thread_id: str) -> None:
        resolved_thread_id = self.normalize_thread_id(thread_id)
        if not resolved_thread_id:
            raise ValueError("thread_id is required")
        thread_paths = self.thread_runtime.resolve(resolved_thread_id)
        if thread_paths.thread_root.is_dir():
            shutil.rmtree(thread_paths.thread_root)
