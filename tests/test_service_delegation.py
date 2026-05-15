from __future__ import annotations

from types import SimpleNamespace

from APP.service.chat_service import ChatService
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
                enabled=False,
                debounce_seconds=30,
                storage_path=sandbox_root / "memory.json",
                model_name=None,
                max_facts=100,
                fact_confidence_threshold=0.7,
                injection_enabled=False,
                max_injection_tokens=1200,
            ),
        )
        self.reminders = ReminderScheduler(sandbox_root / "reminders.json")

    def get_mcp_config(self):
        return {"mcp_servers": {"github": {"enabled": False}}}

    def update_mcp_config(self, mcp_servers):
        return {"mcp_servers": mcp_servers}

    def list_models(self):
        return [{"name": "test", "display_name": "Test", "provider": "fake", "supports_vision": False, "default": True}]

    def list_enabled_skill_names(self):
        return []


def test_chat_service_delegates_mcp_and_model_calls(tmp_path):
    service = ChatService(client=FakeHarnessClient(tmp_path / ".sandbox"))

    assert "github" in service.get_mcp_config()["mcp_servers"]
    assert "playwright" in service.update_mcp_config({"playwright": {"enabled": True}})["mcp_servers"]
    assert service.list_models()[0]["name"] == "test"
