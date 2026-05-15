from __future__ import annotations

from pathlib import Path
from typing import Any, AsyncIterator

from APP.service.chat.service import ChatDomainService
from APP.service.conversation.service import ConversationService
from APP.service.mcp.service import McpService
from APP.service.model.service import ModelService
from APP.service.reminder.service import ReminderService
from APP.service.runtime.service import AppRuntimeService
from harness.client import HarnessClient
from harness.memory import get_memory_queue
from harness.models.types import AgentRunResult
from harness.tools.reminder import Reminder


class ChatService:
    def __init__(self, client: HarnessClient | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        harness_client = client or HarnessClient(project_root=project_root)
        self._runtime = AppRuntimeService(harness_client, memory_queue_getter=lambda config: get_memory_queue(config))
        self._chat = ChatDomainService(self._runtime)
        self._conversation = ConversationService(self._runtime)
        self._mcp = McpService(harness_client)
        self._model = ModelService(harness_client)
        self._reminder = ReminderService(harness_client.reminders)
        self._client = harness_client

    def create_conversation(self, thread_id: str | None = None) -> Any:
        return self._conversation.create_conversation(thread_id)

    def list_conversations(self) -> list[Any]:
        return self._conversation.list_conversations()

    def get_mcp_config(self) -> dict[str, dict[str, object]]:
        return self._mcp.get_mcp_config()

    def update_mcp_config(self, mcp_servers: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
        return self._mcp.update_mcp_config(mcp_servers)

    def get_conversation(self, thread_id: str) -> Any | None:
        return self._conversation.get_conversation(thread_id)

    def rename_conversation(self, thread_id: str, title: str) -> Any:
        return self._conversation.rename_conversation(thread_id, title)

    def delete_conversation(self, thread_id: str) -> None:
        self._conversation.delete_conversation(thread_id)

    async def run_chat(
        self,
        message: str,
        model: str | None = None,
        *,
        thread_id: str | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> AgentRunResult:
        return await self._chat.run_chat(message, model, thread_id=thread_id, messages=messages)

    async def run_chat_stream(
        self,
        message: str,
        model: str | None = None,
        *,
        thread_id: str | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        async for event in self._chat.run_chat_stream(message, model, thread_id=thread_id, messages=messages):
            yield event

    def list_models(self) -> list[dict[str, Any]]:
        return self._model.list_models()

    async def start_reminders(self) -> None:
        await self._reminder.start()

    async def stop_reminders(self) -> None:
        await self._reminder.stop()

    async def get_reminder(self, reminder_id: str) -> Reminder | None:
        return await self._reminder.get_reminder(reminder_id)

    async def list_reminders(self, *, include_cancelled: bool = False) -> list[Reminder]:
        return await self._reminder.list_reminders(include_cancelled=include_cancelled)

    async def update_reminder(
        self,
        reminder_id: str,
        *,
        title: str | None = None,
        message: str | None = None,
        trigger_at: str | None = None,
        timezone: str | None = None,
        recurrence_frequency: str | None = None,
        recurrence_interval: int | None = None,
    ) -> Reminder:
        return await self._reminder.update_reminder(
            reminder_id,
            title=title,
            message=message,
            trigger_at=trigger_at,
            timezone=timezone,
            recurrence_frequency=recurrence_frequency,
            recurrence_interval=recurrence_interval,
        )

    async def delete_reminder(self, reminder_id: str) -> Reminder:
        return await self._reminder.delete_reminder(reminder_id)


_service: ChatService | None = None


def get_chat_service() -> ChatService:
    global _service
    if _service is None:
        _service = ChatService()
    return _service
