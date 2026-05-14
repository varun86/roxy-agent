from __future__ import annotations

from pydantic import BaseModel


class ReminderDetail(BaseModel):
    id: str
    thread_id: str | None = None
    title: str
    message: str
    trigger_at: str
    timezone: str
    status: str
    created_at: str
    fired_at: str | None = None
    delivery_error: str | None = None
