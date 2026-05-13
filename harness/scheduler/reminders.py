from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import URLError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


REMINDER_STATE_PENDING = "pending"
REMINDER_STATE_FIRED = "fired"


@dataclass(slots=True)
class Reminder:
    id: str
    thread_id: str | None
    title: str
    message: str
    trigger_at: str
    timezone: str
    status: str
    created_at: str
    fired_at: str | None = None
    delivery_error: str | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _load_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_reminder(data: object) -> Reminder | None:
    if not isinstance(data, dict):
        return None
    reminder_id = data.get("id")
    title = data.get("title")
    message = data.get("message")
    trigger_at = data.get("trigger_at")
    timezone = data.get("timezone")
    status = data.get("status")
    created_at = data.get("created_at")
    if not all(isinstance(value, str) and value for value in [reminder_id, title, message, trigger_at, timezone, status, created_at]):
        return None
    thread_id = data.get("thread_id")
    fired_at = data.get("fired_at")
    delivery_error = data.get("delivery_error")
    return Reminder(
        id=reminder_id,
        thread_id=thread_id if isinstance(thread_id, str) and thread_id else None,
        title=title,
        message=message,
        trigger_at=trigger_at,
        timezone=timezone,
        status=status,
        created_at=created_at,
        fired_at=fired_at if isinstance(fired_at, str) and fired_at else None,
        delivery_error=delivery_error if isinstance(delivery_error, str) and delivery_error else None,
    )


class ReminderScheduler:
    def __init__(
        self,
        storage_path: Path,
        *,
        delivery_url: str = "http://127.0.0.1:23333/reminder",
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.storage_path = storage_path
        self.delivery_url = delivery_url
        self.poll_interval_seconds = max(0.2, poll_interval_seconds)
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is None:
            return
        await self._task
        self._task = None
        self._stop_event = None

    async def create_reminder(
        self,
        *,
        message: str,
        trigger_at: str,
        timezone: str = "Asia/Shanghai",
        title: str | None = None,
        thread_id: str | None = None,
    ) -> Reminder:
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("message is required")

        trigger_time = self._parse_trigger_at(trigger_at, timezone=timezone)
        if trigger_time <= _utc_now():
            raise ValueError("trigger_at must be in the future")

        reminder = Reminder(
            id=f"reminder-{uuid.uuid4()}",
            thread_id=thread_id.strip() if isinstance(thread_id, str) and thread_id.strip() else None,
            title=(title or "Roxy Reminder").strip() or "Roxy Reminder",
            message=normalized_message,
            trigger_at=trigger_time.isoformat(),
            timezone=timezone.strip() or "Asia/Shanghai",
            status=REMINDER_STATE_PENDING,
            created_at=_utc_now_iso(),
        )
        async with self._lock:
            reminders = self._load_all_unlocked()
            reminders.append(reminder)
            self._save_all_unlocked(reminders)
        return reminder

    async def get_reminder(self, reminder_id: str) -> Reminder | None:
        async with self._lock:
            for reminder in self._load_all_unlocked():
                if reminder.id == reminder_id:
                    return reminder
        return None

    async def list_reminders(self) -> list[Reminder]:
        async with self._lock:
            return self._load_all_unlocked()

    def _load_all_unlocked(self) -> list[Reminder]:
        payload = _load_json(self.storage_path)
        if not isinstance(payload, list):
            return []
        reminders: list[Reminder] = []
        for item in payload:
            reminder = _parse_reminder(item)
            if reminder is not None:
                reminders.append(reminder)
        return reminders

    def _save_all_unlocked(self, reminders: list[Reminder]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in reminders]
        self.storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    async def _run_loop(self) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            await self._fire_due_reminders()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
            except TimeoutError:
                continue

    async def _fire_due_reminders(self) -> None:
        due: list[Reminder] = []
        async with self._lock:
            reminders = self._load_all_unlocked()
            now = _utc_now()
            for reminder in reminders:
                if reminder.status != REMINDER_STATE_PENDING:
                    continue
                try:
                    trigger_time = datetime.fromisoformat(reminder.trigger_at)
                except ValueError:
                    continue
                if trigger_time <= now:
                    due.append(reminder)

        for reminder in due:
            delivery_error = await self._deliver_reminder(reminder)
            async with self._lock:
                reminders = self._load_all_unlocked()
                for item in reminders:
                    if item.id == reminder.id:
                        item.status = REMINDER_STATE_FIRED
                        item.fired_at = _utc_now_iso()
                        item.delivery_error = delivery_error
                        break
                self._save_all_unlocked(reminders)

    async def _deliver_reminder(self, reminder: Reminder) -> str | None:
        payload = json.dumps(
            {
                "id": reminder.id,
                "thread_id": reminder.thread_id,
                "title": reminder.title,
                "message": reminder.message,
                "trigger_at": reminder.trigger_at,
                "timezone": reminder.timezone,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        def post() -> str | None:
            req = request.Request(
                self.delivery_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=2) as response:
                    if 200 <= response.status < 300:
                        return None
                    return f"HTTP {response.status}"
            except (OSError, URLError) as exc:
                return str(exc)

        return await asyncio.to_thread(post)

    @staticmethod
    def _parse_trigger_at(value: str, *, timezone: str) -> datetime:
        raw = value.strip()
        if not raw:
            raise ValueError("trigger_at is required")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("trigger_at must be an ISO 8601 datetime") from exc

        if parsed.tzinfo is None:
            try:
                tz = ZoneInfo(timezone.strip() or "Asia/Shanghai")
            except ZoneInfoNotFoundError as exc:
                raise ValueError(f"Unknown timezone: {timezone}") from exc
            parsed = parsed.replace(tzinfo=tz)
        return parsed.astimezone(UTC)
