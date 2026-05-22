from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from APP.service.chat_service import ChatService
from harness.context import normalize_thread_id
from harness.models.types import AgentRunResult, AgentTrace
from harness.tools.reminder import ReminderScheduler


class FakeHarnessClient:
    def __init__(self, sandbox_root) -> None:
        self.config = SimpleNamespace(
            sandbox=SimpleNamespace(root_dir=sandbox_root),
            runtime=SimpleNamespace(
                max_recent_messages=8,
                compact_threshold_chars=5000,
                skill_memory_max=4,
            ),
            memory=SimpleNamespace(
                enabled=True,
                debounce_seconds=30,
                storage_path=sandbox_root / "memory.json",
                model_name=None,
                max_facts=100,
                fact_confidence_threshold=0.7,
                injection_enabled=True,
                max_injection_tokens=1200,
            ),
        )
        self.reminders = ReminderScheduler(sandbox_root / "reminders.json")
        self.calls: list[dict[str, object]] = []

    async def run_async(self, prompt: str, model_name: str | None = None, **kwargs) -> AgentRunResult:
        self.calls.append({"prompt": prompt, "model_name": model_name, **kwargs})
        return AgentRunResult(text=f"reply:{prompt}")

    def list_enabled_skill_names(self) -> list[str]:
        return ["example"]

    def list_models(self) -> list[dict[str, object]]:
        return []


class FakeStreamingHarnessClient(FakeHarnessClient):
    async def run_async(self, prompt: str, model_name: str | None = None, **kwargs) -> AgentRunResult:
        event_callback = kwargs.get("event_callback")
        on_text_delta = kwargs.get("on_text_delta")
        if event_callback is not None:
            await event_callback(
                {
                    "type": "tool_called",
                    "call_id": "call_1",
                    "tool_name": "read_file",
                    "arguments": {"path": "README.md"},
                    "output": "hello",
                    "is_error": False,
                }
            )
        if event_callback is not None:
            await event_callback(
                {
                    "type": "task_started",
                    "task_id": "task_1",
                    "description": "inspect",
                    "subagent_type": "general-purpose",
                }
            )
        if on_text_delta is not None:
            await on_text_delta("hello")
        if event_callback is not None:
            await event_callback({"type": "task_completed", "task_id": "task_1", "result": "done"})
        return AgentRunResult(text="hello", trace=AgentTrace(tool_calls=1))


class FakeTtsMarkerHarnessClient(FakeHarnessClient):
    async def run_async(self, prompt: str, model_name: str | None = None, **kwargs) -> AgentRunResult:
        self.calls.append({"prompt": prompt, "model_name": model_name, **kwargs})
        return AgentRunResult(text="整理好了。\n<roxy_tts_ja>はい、きちんと整えました。</roxy_tts_ja>")


@pytest.mark.asyncio
async def test_chat_service_routes_context_by_thread_id(tmp_path):
    client = FakeHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    queue_calls: list[dict[str, object]] = []
    fake_queue = SimpleNamespace(add=lambda **kwargs: queue_calls.append(kwargs))
    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        result = await service.run_chat("hello", thread_id="thread-a")

    assert result.text == "reply:hello"
    assert result.thread_id == "thread-a"
    assert client.calls[0]["thread_id"] == "thread-a"
    assert queue_calls[0]["thread_id"] == "thread-a"
    thread_root = tmp_path / ".sandbox" / "threads" / normalize_thread_id("thread-a")
    thread_context = thread_root / "context.json"
    assert thread_context.exists()
    assert (thread_root / "conversation.json").exists()
    assert (thread_root / "messages.json").exists()


@pytest.mark.asyncio
async def test_chat_service_isolates_context_between_threads(tmp_path):
    client = FakeHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)
    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        await service.run_chat("first", thread_id="thread-a")
        await service.run_chat("second", thread_id="thread-b")

    first_context = tmp_path / ".sandbox" / "threads" / normalize_thread_id("thread-a") / "context.json"
    second_context = tmp_path / ".sandbox" / "threads" / normalize_thread_id("thread-b") / "context.json"
    assert first_context.exists()
    assert second_context.exists()
    assert first_context.read_text(encoding="utf-8") != second_context.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_chat_service_does_not_create_legacy_runtime_context_dir(tmp_path):
    client = FakeHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)
    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        await service.run_chat("hello", thread_id="thread-a")

    assert not (tmp_path / ".runtime").exists()


@pytest.mark.asyncio
async def test_chat_service_stream_emits_subagent_events(tmp_path):
    client = FakeStreamingHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)
    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        events = [event async for event in service.run_chat_stream("hello", thread_id="thread-a")]

    assert events[0]["type"] == "start"
    assert any(event["type"] == "task_started" for event in events)
    assert any(event["type"] == "task_completed" for event in events)
    done_event = events[-1]
    assert done_event["type"] == "done"
    assert done_event["thread_id"] == "thread-a"
    assert done_event["trace"]["subagent_calls"] == 0

    detail = service.get_conversation("thread-a")
    assert detail is not None
    assistant_message = detail.messages[1]
    assert assistant_message.tool_events[0].tool_name == "read_file"
    assert assistant_message.trace is not None
    assert assistant_message.trace.tool_calls == 1


@pytest.mark.asyncio
async def test_chat_service_creates_thread_id_when_missing(tmp_path):
    client = FakeHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)
    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        result = await service.run_chat("hello")

    assert result.thread_id is not None
    assert result.thread_id.startswith("thread-")
    assert client.calls[0]["thread_id"] == result.thread_id


@pytest.mark.asyncio
async def test_chat_service_appends_full_history_and_reuses_it(tmp_path):
    client = FakeHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)
    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        await service.run_chat("first", thread_id="thread-a")
        await service.run_chat("second", thread_id="thread-a")

    thread_root = tmp_path / ".sandbox" / "threads" / normalize_thread_id("thread-a")
    messages = json.loads((thread_root / "messages.json").read_text(encoding="utf-8"))

    assert [item["content"] for item in messages] == [
        "first",
        "reply:first",
        "second",
        "reply:second",
    ]
    history = client.calls[1]["conversation_history"]
    assert history == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply:first"},
    ]


@pytest.mark.asyncio
async def test_chat_service_lists_gets_and_renames_conversations(tmp_path):
    client = FakeHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)

    created = service.create_conversation()
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)
    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        await service.run_chat("hello there", thread_id=created.thread_id)

    summaries = service.list_conversations()
    assert len(summaries) == 1
    assert summaries[0].thread_id == created.thread_id

    detail = service.get_conversation(created.thread_id)
    assert detail is not None
    assert detail.summary.title == "hello there"
    assert len(detail.messages) == 2

    renamed = service.rename_conversation(created.thread_id, "Renamed Session")
    assert renamed.title == "Renamed Session"
    refreshed = service.get_conversation(created.thread_id)
    assert refreshed is not None
    assert refreshed.summary.title == "Renamed Session"


@pytest.mark.asyncio
async def test_chat_service_memory_queue_failure_does_not_break_chat(tmp_path):
    client = FakeHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    fake_queue = SimpleNamespace(add=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("queue failed")))
    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        result = await service.run_chat("hello", thread_id="thread-a")

    assert result.text == "reply:hello"


@pytest.mark.asyncio
async def test_chat_service_skips_realtime_tts_plugin_when_disabled(tmp_path):
    client = FakeHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    plugin = service._runtime.plugin_manager.get_plugin("roxy_realtime_tts")
    plugin.enabled = False
    synthesize = AsyncMock()
    plugin.synthesize_and_play = synthesize
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)

    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        await service.run_chat("hello", thread_id="thread-a")
        await asyncio.sleep(0)

    synthesize.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_service_runs_realtime_tts_plugin_after_reply(tmp_path):
    client = FakeTtsMarkerHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    plugin = service._runtime.plugin_manager.get_plugin("roxy_realtime_tts")
    plugin.enabled = True
    synthesize = AsyncMock(return_value={"output_path": "/tmp/roxy.wav"})
    plugin.synthesize_and_play = synthesize
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)

    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        await service.run_chat("hello", thread_id="thread-a")
        await asyncio.sleep(0)

    assert client.calls[0]["realtime_tts_enabled"] is True
    assert service.get_conversation("thread-a").messages[1].content == "整理好了。"
    synthesize.assert_awaited_once_with("はい、きちんと整えました。")


@pytest.mark.asyncio
async def test_chat_service_realtime_tts_falls_back_when_marker_missing(tmp_path):
    client = FakeHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    plugin = service._runtime.plugin_manager.get_plugin("roxy_realtime_tts")
    plugin.enabled = True
    synthesize = AsyncMock(return_value={"output_path": "/tmp/roxy.wav"})
    plugin.synthesize_and_play = synthesize
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)

    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        await service.run_chat("hello", thread_id="thread-a")
        await asyncio.sleep(0)

    assert service.get_conversation("thread-a").messages[1].content == "reply:hello"
    synthesize.assert_awaited_once_with("はい、整いました。")


@pytest.mark.asyncio
async def test_chat_service_does_not_request_tts_marker_when_plugin_disabled(tmp_path):
    client = FakeHarnessClient(tmp_path / ".sandbox")
    service = ChatService(client=client)
    plugin = service._runtime.plugin_manager.get_plugin("roxy_realtime_tts")
    plugin.enabled = False
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)

    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        await service.run_chat("hello", thread_id="thread-a")

    assert client.calls[0]["realtime_tts_enabled"] is False
