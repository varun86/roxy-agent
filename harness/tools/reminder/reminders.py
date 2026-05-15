from __future__ import annotations

import asyncio
import calendar
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib import request
from urllib.error import URLError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


REMINDER_STATE_PENDING = "pending"
REMINDER_STATE_COMPLETED = "completed"
REMINDER_STATE_CANCELLED = "cancelled"
REMINDER_KIND_ONE_TIME = "one_time"
REMINDER_KIND_RECURRING = "recurring"
REMINDER_RECURRENCE_DAILY = "daily"
REMINDER_RECURRENCE_WEEKLY = "weekly"
REMINDER_RECURRENCE_MONTHLY = "monthly"
VALID_RECURRENCE_FREQUENCIES = {
    REMINDER_RECURRENCE_DAILY,
    REMINDER_RECURRENCE_WEEKLY,
    REMINDER_RECURRENCE_MONTHLY,
}


@dataclass(slots=True)
class ReminderRecurrence:
    frequency: str
    interval: int = 1


@dataclass(slots=True)
class Reminder:
    id: str
    thread_id: str | None
    title: str
    message: str
    trigger_at: str
    timezone: str
    kind: str
    recurrence: ReminderRecurrence | None
    status: str
    created_at: str
    updated_at: str
    fired_at: str | None = None
    last_fired_at: str | None = None
    cancelled_at: str | None = None
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
    updated_at = data.get("updated_at")
    if not all(isinstance(value, str) and value for value in [reminder_id, title, message, trigger_at, timezone, status, created_at]):
        return None
    recurrence = _parse_recurrence(data.get("recurrence"))
    kind = data.get("kind")
    if kind not in {REMINDER_KIND_ONE_TIME, REMINDER_KIND_RECURRING}:
        kind = REMINDER_KIND_RECURRING if recurrence is not None else REMINDER_KIND_ONE_TIME
    if kind == REMINDER_KIND_RECURRING and recurrence is None:
        return None
    thread_id = data.get("thread_id")
    fired_at = data.get("fired_at")
    last_fired_at = data.get("last_fired_at")
    cancelled_at = data.get("cancelled_at")
    delivery_error = data.get("delivery_error")
    return Reminder(
        id=reminder_id,
        thread_id=thread_id if isinstance(thread_id, str) and thread_id else None,
        title=title,
        message=message,
        trigger_at=trigger_at,
        timezone=timezone,
        kind=kind,
        recurrence=recurrence,
        status=status,
        created_at=created_at,
        updated_at=updated_at if isinstance(updated_at, str) and updated_at else created_at,
        fired_at=fired_at if isinstance(fired_at, str) and fired_at else None,
        last_fired_at=last_fired_at if isinstance(last_fired_at, str) and last_fired_at else None,
        cancelled_at=cancelled_at if isinstance(cancelled_at, str) and cancelled_at else None,
        delivery_error=delivery_error if isinstance(delivery_error, str) and delivery_error else None,
    )


def _parse_recurrence(data: object) -> ReminderRecurrence | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return None
    frequency = data.get("frequency")
    interval = data.get("interval", 1)
    if not isinstance(frequency, str) or frequency not in VALID_RECURRENCE_FREQUENCIES:
        return None
    if not isinstance(interval, int) or interval < 1:
        return None
    return ReminderRecurrence(frequency=frequency, interval=interval)


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
        recurrence_frequency: str | None = None,
        recurrence_interval: int = 1,
    ) -> Reminder:
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("message is required")

        normalized_timezone = timezone.strip() or "Asia/Shanghai"
        trigger_time = self._parse_trigger_at(trigger_at, timezone=normalized_timezone)
        if trigger_time <= _utc_now():
            raise ValueError("trigger_at must be in the future")
        recurrence = self._build_recurrence(
            recurrence_frequency=recurrence_frequency,
            recurrence_interval=recurrence_interval,
        )
        now_iso = _utc_now_iso()

        reminder = Reminder(
            id=f"reminder-{uuid.uuid4()}",
            thread_id=thread_id.strip() if isinstance(thread_id, str) and thread_id.strip() else None,
            title=(title or "Roxy Reminder").strip() or "Roxy Reminder",
            message=normalized_message,
            trigger_at=trigger_time.isoformat(),
            timezone=normalized_timezone,
            kind=REMINDER_KIND_RECURRING if recurrence is not None else REMINDER_KIND_ONE_TIME,
            recurrence=recurrence,
            status=REMINDER_STATE_PENDING,
            created_at=now_iso,
            updated_at=now_iso,
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

    async def list_reminders(self, *, include_cancelled: bool = False) -> list[Reminder]:
        async with self._lock:
            reminders = self._load_all_unlocked()
        if include_cancelled:
            return reminders
        return [item for item in reminders if item.status != REMINDER_STATE_CANCELLED]

    async def update_reminder(
        self,
        reminder_id: str,
        *,
        message: str | None = None,
        trigger_at: str | None = None,
        timezone: str | None = None,
        title: str | None = None,
        recurrence_frequency: str | None = None,
        recurrence_interval: int | None = None,
    ) -> Reminder:
        async with self._lock:
            reminders = self._load_all_unlocked()
            reminder = next((item for item in reminders if item.id == reminder_id), None)
            if reminder is None:
                raise KeyError(reminder_id)
            if reminder.status != REMINDER_STATE_PENDING:
                raise ValueError("Only pending reminders can be updated")

            next_timezone = (timezone.strip() if isinstance(timezone, str) else reminder.timezone) or reminder.timezone
            next_message = message.strip() if isinstance(message, str) else reminder.message
            next_title = title.strip() if isinstance(title, str) else reminder.title
            if not next_message:
                raise ValueError("message is required")
            if not next_title:
                raise ValueError("title is required")

            frequency_marker = recurrence_frequency
            interval_marker = recurrence_interval
            if frequency_marker is None and interval_marker is None:
                next_recurrence = reminder.recurrence
            else:
                next_recurrence = self._build_recurrence(
                    recurrence_frequency=frequency_marker,
                    recurrence_interval=interval_marker if interval_marker is not None else 1,
                )
            next_trigger_source = trigger_at if isinstance(trigger_at, str) else reminder.trigger_at
            next_trigger_at = self._parse_trigger_at(next_trigger_source, timezone=next_timezone)
            if next_trigger_at <= _utc_now():
                raise ValueError("trigger_at must be in the future")

            reminder.message = next_message
            reminder.title = next_title
            reminder.timezone = next_timezone
            reminder.trigger_at = next_trigger_at.isoformat()
            reminder.recurrence = next_recurrence
            reminder.kind = REMINDER_KIND_RECURRING if next_recurrence is not None else REMINDER_KIND_ONE_TIME
            reminder.updated_at = _utc_now_iso()
            reminder.delivery_error = None
            self._save_all_unlocked(reminders)
            return reminder

    async def delete_reminder(self, reminder_id: str) -> Reminder:
        async with self._lock:
            reminders = self._load_all_unlocked()
            reminder = next((item for item in reminders if item.id == reminder_id), None)
            if reminder is None:
                raise KeyError(reminder_id)
            if reminder.status == REMINDER_STATE_CANCELLED:
                return reminder
            now_iso = _utc_now_iso()
            reminder.status = REMINDER_STATE_CANCELLED
            reminder.cancelled_at = now_iso
            reminder.updated_at = now_iso
            self._save_all_unlocked(reminders)
            return reminder

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
                        fired_at = _utc_now_iso()
                        item.fired_at = fired_at
                        item.last_fired_at = fired_at
                        item.delivery_error = delivery_error
                        item.updated_at = fired_at
                        if item.recurrence is None:
                            item.status = REMINDER_STATE_COMPLETED
                        else:
                            item.trigger_at = self._compute_next_trigger_at(item).isoformat()
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

    @staticmethod
    def _build_recurrence(*, recurrence_frequency: str | None, recurrence_interval: int) -> ReminderRecurrence | None:
        if recurrence_frequency is None:
            return None
        normalized = recurrence_frequency.strip().lower()
        if not normalized:
            return None
        if normalized not in VALID_RECURRENCE_FREQUENCIES:
            raise ValueError(f"Unsupported recurrence frequency: {recurrence_frequency}")
        if recurrence_interval < 1:
            raise ValueError("recurrence_interval must be at least 1")
        return ReminderRecurrence(frequency=normalized, interval=recurrence_interval)

    @staticmethod
    def _compute_next_trigger_at(reminder: Reminder) -> datetime:
        if reminder.recurrence is None:
            raise ValueError("recurring reminder required")
        try:
            tz = ZoneInfo(reminder.timezone.strip() or "Asia/Shanghai")
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {reminder.timezone}") from exc
        current_local = datetime.fromisoformat(reminder.trigger_at).astimezone(tz)
        recurrence = reminder.recurrence
        assert recurrence is not None
        if recurrence.frequency == REMINDER_RECURRENCE_DAILY:
            next_local = current_local.replace() + timedelta(days=recurrence.interval)
        elif recurrence.frequency == REMINDER_RECURRENCE_WEEKLY:
            next_local = current_local.replace() + timedelta(weeks=recurrence.interval)
        else:
            next_local = ReminderScheduler._add_months(current_local, recurrence.interval)
        return next_local.astimezone(UTC)

    @staticmethod
    def _add_months(value: datetime, months: int) -> datetime:
        total_month = (value.month - 1) + months
        year = value.year + total_month // 12
        month = total_month % 12 + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)
