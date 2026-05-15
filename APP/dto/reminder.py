from __future__ import annotations

from pydantic import BaseModel


class ReminderRecurrencePayload(BaseModel):
    frequency: str
    interval: int


class ReminderDetail(BaseModel):
    id: str
    thread_id: str | None = None
    title: str
    message: str
    trigger_at: str
    timezone: str
    kind: str
    recurrence: ReminderRecurrencePayload | None = None
    status: str
    created_at: str
    updated_at: str
    fired_at: str | None = None
    last_fired_at: str | None = None
    cancelled_at: str | None = None
    delivery_error: str | None = None


class ReminderUpdateRequest(BaseModel):
    reminder_id: str
    title: str | None = None
    message: str | None = None
    trigger_at: str | None = None
    timezone: str | None = None
    recurrence_frequency: str | None = None
    recurrence_interval: int | None = None


class ReminderDeleteRequest(BaseModel):
    reminder_id: str
