from __future__ import annotations

import asyncio
from typing import AsyncIterator

from APP.service.runtime.service import AppRuntimeService
from harness.models.types import AgentRunResult


class ChatDomainService:
    def __init__(self, runtime: AppRuntimeService) -> None:
        self.runtime = runtime

    async def run_chat(
        self,
        message: str,
        model: str | None = None,
        *,
        thread_id: str | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> AgentRunResult:
        resolved_thread_id = self.runtime.resolve_or_create_thread_id(thread_id)
        lock = self.runtime.get_thread_lock(resolved_thread_id)
        async with lock:
            thread_paths = self.runtime.thread_runtime.ensure_dirs(self.runtime.thread_runtime.resolve(resolved_thread_id))
            self.runtime.conversation_store.ensure_conversation(
                resolved_thread_id,
                conversation_path=thread_paths.conversation_file,
                messages_path=thread_paths.messages_file,
            )
            context = self.runtime.context_store.load(resolved_thread_id, context_path=thread_paths.context_file)
            history = self.runtime.build_history(resolved_thread_id, messages=messages)

            tool_events = []

            async def on_event(event: dict[str, object]) -> None:
                tool_event = self.runtime.build_tool_event(event)
                if tool_event is not None:
                    tool_events.append(tool_event)

            realtime_prompt_text = self.runtime.get_realtime_prompt_text()
            result = await self.runtime.client.run_async(
                message,
                model,
                conversation_history=history,
                thread_id=resolved_thread_id,
                thread_paths=thread_paths,
                pinned_skills=context.pinned_skills,
                compact_summary=context.compact_summary,
                event_callback=on_event,
                realtime_tts_enabled=bool(realtime_prompt_text),
                realtime_tts_prompt=realtime_prompt_text,
            )
            visible_text, control_payloads = self.runtime.plugin_manager.extract_control_payloads(result.text)
            result.text = visible_text

            self.runtime.context_store.update_after_turn(
                context,
                user_message=message,
                assistant_message=result.text,
                incoming_messages=messages,
                available_skill_names=self.runtime.client.list_enabled_skill_names(),
                context_path=thread_paths.context_file,
            )
            trace_info = self.runtime.build_trace_info(result)
            self.runtime.conversation_store.append_turn(
                resolved_thread_id,
                user_message=message,
                assistant_message=result.text,
                assistant_tool_events=tool_events,
                assistant_trace=trace_info,
                conversation_path=thread_paths.conversation_file,
                messages_path=thread_paths.messages_file,
            )
            self.runtime.queue_memory_update(
                thread_id=resolved_thread_id,
                user_message=message,
                assistant_message=result.text,
                history=history,
            )
            result.thread_id = resolved_thread_id
            asyncio.create_task(self.runtime.run_after_assistant_message_hooks(
                visible_text=result.text,
                control_payloads=control_payloads,
                thread_id=resolved_thread_id,
                trace=trace_info,
            ))
            return result

    async def run_chat_stream(
        self,
        message: str,
        model: str | None = None,
        *,
        thread_id: str | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        yield {"type": "start"}

        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        tool_events = []

        async def on_text_delta(delta: str) -> None:
            await queue.put({"type": "delta", "delta": delta})

        async def on_event(event: dict[str, object]) -> None:
            tool_event = self.runtime.build_tool_event(event)
            if tool_event is not None:
                tool_events.append(tool_event)
            await queue.put(event)

        resolved_thread_id = self.runtime.resolve_or_create_thread_id(thread_id)
        lock = self.runtime.get_thread_lock(resolved_thread_id)
        async with lock:
            thread_paths = self.runtime.thread_runtime.ensure_dirs(self.runtime.thread_runtime.resolve(resolved_thread_id))
            self.runtime.conversation_store.ensure_conversation(
                resolved_thread_id,
                conversation_path=thread_paths.conversation_file,
                messages_path=thread_paths.messages_file,
            )
            context = self.runtime.context_store.load(resolved_thread_id, context_path=thread_paths.context_file)
            history = self.runtime.build_history(resolved_thread_id, messages=messages)
            realtime_prompt_text = self.runtime.get_realtime_prompt_text()
            task = asyncio.create_task(
                self.runtime.client.run_async(
                    message,
                    model,
                    on_text_delta=on_text_delta,
                    conversation_history=history,
                    thread_id=resolved_thread_id,
                    thread_paths=thread_paths,
                    pinned_skills=context.pinned_skills,
                    compact_summary=context.compact_summary,
                    event_callback=on_event,
                    realtime_tts_enabled=bool(realtime_prompt_text),
                    realtime_tts_prompt=realtime_prompt_text,
                )
            )

            while True:
                if task.done() and queue.empty():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.05)
                    yield event
                except TimeoutError:
                    continue

            result = await task
            visible_text, control_payloads = self.runtime.plugin_manager.extract_control_payloads(result.text)
            result.text = visible_text
            self.runtime.context_store.update_after_turn(
                context,
                user_message=message,
                assistant_message=result.text,
                incoming_messages=messages,
                available_skill_names=self.runtime.client.list_enabled_skill_names(),
                context_path=thread_paths.context_file,
            )
            trace_info = self.runtime.build_trace_info(result)
            self.runtime.conversation_store.append_turn(
                resolved_thread_id,
                user_message=message,
                assistant_message=result.text,
                assistant_tool_events=tool_events,
                assistant_trace=trace_info,
                conversation_path=thread_paths.conversation_file,
                messages_path=thread_paths.messages_file,
            )
            self.runtime.queue_memory_update(
                thread_id=resolved_thread_id,
                user_message=message,
                assistant_message=result.text,
                history=history,
            )
            result.thread_id = resolved_thread_id
            asyncio.create_task(self.runtime.run_after_assistant_message_hooks(
                visible_text=result.text,
                control_payloads=control_payloads,
                thread_id=resolved_thread_id,
                trace=trace_info,
            ))

        yield {
            "type": "done",
            "text": result.text,
            "trace": {
                "steps": result.trace.steps,
                "tool_calls": result.trace.tool_calls,
                "errors": result.trace.errors,
                "subagent_calls": result.trace.subagent_calls,
                "subagent_errors": result.trace.subagent_errors,
            },
            "thread_id": resolved_thread_id,
        }
