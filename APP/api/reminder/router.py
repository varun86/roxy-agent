from __future__ import annotations

from fastapi import APIRouter, HTTPException

from APP.dto import ReminderDetail
from APP.service import get_chat_service

router = APIRouter(prefix="", tags=["reminder"])


@router.get("/reminders/{reminder_id}", response_model=ReminderDetail, summary="Get reminder details")
async def get_reminder(reminder_id: str) -> ReminderDetail:
    service = get_chat_service()
    reminder = await service.get_reminder(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail=f"Reminder not found: {reminder_id}")
    return ReminderDetail(
        id=reminder.id,
        thread_id=reminder.thread_id,
        title=reminder.title,
        message=reminder.message,
        trigger_at=reminder.trigger_at,
        timezone=reminder.timezone,
        status=reminder.status,
        created_at=reminder.created_at,
        fired_at=reminder.fired_at,
        delivery_error=reminder.delivery_error,
    )
