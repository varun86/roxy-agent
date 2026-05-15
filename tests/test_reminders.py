from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from harness.tools.reminder import ReminderScheduler


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
    assert loaded.kind == "one_time"
    assert loaded.updated_at == loaded.created_at


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
        assert fired.status == "completed"
        assert fired.fired_at is not None
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_recurring_reminder_advances_after_firing(tmp_path):
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
        scheduler = ReminderScheduler(tmp_path / "reminders.json", delivery_url=url)
        created = await scheduler.create_reminder(
            title="Hydrate",
            message="Drink water",
            trigger_at=(datetime.now(UTC) + timedelta(seconds=1)).isoformat(),
            recurrence_frequency="daily",
        )
        created.trigger_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        scheduler._save_all_unlocked([created])

        previous_trigger_at = created.trigger_at
        await scheduler._fire_due_reminders()
        updated = await scheduler.get_reminder(created.id)

        assert received[0]["id"] == created.id
        assert updated is not None
        assert updated.status == "pending"
        assert updated.recurrence is not None
        assert updated.recurrence.frequency == "daily"
        assert updated.trigger_at != previous_trigger_at
        assert updated.last_fired_at is not None
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_reminder_scheduler_updates_and_cancels(tmp_path):
    scheduler = ReminderScheduler(tmp_path / "reminders.json")
    created = await scheduler.create_reminder(
        title="Hydrate",
        message="Drink water",
        trigger_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
    )

    updated = await scheduler.update_reminder(
        created.id,
        message="Drink more water",
        recurrence_frequency="weekly",
        recurrence_interval=2,
    )
    deleted = await scheduler.delete_reminder(created.id)
    reminders = await scheduler.list_reminders()
    reminders_with_cancelled = await scheduler.list_reminders(include_cancelled=True)

    assert updated.message == "Drink more water"
    assert updated.kind == "recurring"
    assert updated.recurrence is not None
    assert updated.recurrence.frequency == "weekly"
    assert updated.recurrence.interval == 2
    assert deleted.status == "cancelled"
    assert deleted.cancelled_at is not None
    assert reminders == []
    assert reminders_with_cancelled[0].status == "cancelled"
