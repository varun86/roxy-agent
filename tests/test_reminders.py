from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from harness.scheduler import ReminderScheduler


@pytest.mark.asyncio
async def test_reminder_scheduler_persists_and_loads_reminder(tmp_path):
    scheduler = ReminderScheduler(tmp_path / "reminders.json")
    trigger_at = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()

    created = await scheduler.create_reminder(
        title="Hydrate",
        message="Drink water",
        trigger_at=trigger_at,
        thread_id="thread-a",
    )
    loaded = await scheduler.get_reminder(created.id)

    assert loaded is not None
    assert loaded.title == "Hydrate"
    assert loaded.message == "Drink water"
    assert loaded.thread_id == "thread-a"
    assert loaded.status == "pending"


@pytest.mark.asyncio
async def test_reminder_scheduler_rejects_past_time(tmp_path):
    scheduler = ReminderScheduler(tmp_path / "reminders.json")
    trigger_at = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()

    with pytest.raises(ValueError, match="future"):
        await scheduler.create_reminder(message="Too late", trigger_at=trigger_at)


@pytest.mark.asyncio
async def test_reminder_scheduler_fires_due_reminder(tmp_path):
    received: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            received.append(json.loads(self.rfile.read(length).decode("utf-8")))
            self.send_response(204)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/reminder"
        storage_path = tmp_path / "reminders.json"
        due_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        storage_path.write_text(
            json.dumps(
                [
                    {
                        "id": "reminder-test",
                        "thread_id": "thread-a",
                        "title": "Hydrate",
                        "message": "Drink water",
                        "trigger_at": due_at,
                        "timezone": "Asia/Shanghai",
                        "status": "pending",
                        "created_at": due_at,
                    }
                ]
            ),
            encoding="utf-8",
        )
        scheduler = ReminderScheduler(storage_path, delivery_url=url)

        await scheduler._fire_due_reminders()
        fired = await scheduler.get_reminder("reminder-test")

        assert received[0]["id"] == "reminder-test"
        assert received[0]["thread_id"] == "thread-a"
        assert fired is not None
        assert fired.status == "fired"
        assert fired.fired_at is not None
    finally:
        server.shutdown()
        thread.join(timeout=2)
