from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import APP.api.app as app_module
import APP.service.chat_service as chat_service_module
from APP.api.app import create_app
from APP.service.chat_service import ChatService
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
        self.mcp_config = {
            "mcp_servers": {
                "github": {
                    "enabled": False,
                    "type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": ""},
                    "description": "GitHub MCP server",
                }
            }
        }

    async def run_async(self, prompt: str, model_name: str | None = None, **kwargs) -> AgentRunResult:
        event_callback = kwargs.get("event_callback")
        if event_callback is not None:
            await event_callback(
                {
                    "type": "tool_called",
                    "call_id": "call-1",
                    "tool_name": "read_file",
                    "arguments": {"path": "README.md"},
                    "output": "hello",
                    "is_error": False,
                }
            )
        return AgentRunResult(text=f"reply:{prompt}", trace=AgentTrace(steps=2, tool_calls=1))

    def list_enabled_skill_names(self) -> list[str]:
        return ["example"]

    def list_models(self) -> list[dict[str, object]]:
        return []

    def get_mcp_config(self) -> dict[str, dict[str, object]]:
        return self.mcp_config

    def update_mcp_config(self, mcp_servers: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
        self.mcp_config = {"mcp_servers": mcp_servers}
        return self.mcp_config


def test_conversation_endpoints_work(tmp_path):
    service = ChatService(client=FakeHarnessClient(tmp_path / ".sandbox"))
    app_module._service = service
    chat_service_module._service = service
    client = TestClient(create_app())
    fake_queue = SimpleNamespace(add=lambda **kwargs: None)

    with patch("APP.service.chat_service.get_memory_queue", return_value=fake_queue):
        create_response = client.post("/conversations/create")
        assert create_response.status_code == 200
        created = create_response.json()
        thread_id = created["thread_id"]

        chat_response = client.post("/chat", json={"message": "hello", "thread_id": thread_id})
        assert chat_response.status_code == 200
        assert chat_response.json()["thread_id"] == thread_id

        list_response = client.get("/conversations")
        assert list_response.status_code == 200
        summaries = list_response.json()
        assert summaries[0]["thread_id"] == thread_id

        detail_response = client.get(f"/conversations/{thread_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["messages"][0]["content"] == "hello"
        assert detail["messages"][1]["tool_events"][0]["tool_name"] == "read_file"
        assert detail["messages"][1]["trace"]["tool_calls"] == 1

        rename_response = client.post(
            f"/conversations/{thread_id}/rename",
            json={"title": "Renamed"},
        )
        assert rename_response.status_code == 200
        assert rename_response.json()["title"] == "Renamed"


def test_reminder_endpoint_returns_detail(tmp_path):
    service = ChatService(client=FakeHarnessClient(tmp_path / ".sandbox"))
    app_module._service = service
    chat_service_module._service = service
    client = TestClient(create_app())
    reminder = client.post("/chat", json={"message": "noop", "thread_id": "thread-a"})
    assert reminder.status_code == 200

    import asyncio
    from datetime import UTC, datetime, timedelta

    created = asyncio.run(
        service._client.reminders.create_reminder(
            title="Hydrate",
            message="Drink water",
            trigger_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            thread_id="thread-a",
        )
    )

    response = client.get(f"/reminders/{created.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == created.id
    assert payload["message"] == "Drink water"
    assert payload["kind"] == "one_time"


def test_reminder_endpoints_support_list_update_and_delete(tmp_path):
    service = ChatService(client=FakeHarnessClient(tmp_path / ".sandbox"))
    app_module._service = service
    chat_service_module._service = service
    client = TestClient(create_app())

    import asyncio
    from datetime import UTC, datetime, timedelta

    created = asyncio.run(
        service._client.reminders.create_reminder(
            title="Hydrate",
            message="Drink water",
            trigger_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            thread_id="thread-a",
        )
    )

    list_response = client.get("/reminders")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == created.id

    update_response = client.post(
        "/reminders/update",
        json={
            "reminder_id": created.id,
            "message": "Drink warm water",
            "recurrence_frequency": "daily",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["message"] == "Drink warm water"
    assert update_response.json()["kind"] == "recurring"

    delete_response = client.post("/reminders/delete", json={"reminder_id": created.id})
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "cancelled"

    list_with_cancelled = client.get("/reminders", params={"include_cancelled": "true"})
    assert list_with_cancelled.status_code == 200
    assert list_with_cancelled.json()[0]["status"] == "cancelled"


def test_mcp_config_endpoints_work(tmp_path):
    service = ChatService(client=FakeHarnessClient(tmp_path / ".sandbox"))
    app_module._service = service
    chat_service_module._service = service
    client = TestClient(create_app())

    get_response = client.get("/mcp/config")
    assert get_response.status_code == 200
    assert "github" in get_response.json()["mcp_servers"]

    update_response = client.post(
        "/mcp/config",
        json={
            "mcp_servers": {
                "playwright": {
                    "enabled": True,
                    "type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@playwright/mcp"],
                    "description": "Playwright MCP server",
                }
            }
        },
    )
    assert update_response.status_code == 200
    assert "playwright" in update_response.json()["mcp_servers"]
