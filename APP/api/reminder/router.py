from __future__ import annotations

from fastapi import APIRouter, HTTPException

from APP.dto import ReminderDeleteRequest, ReminderDetail, ReminderUpdateRequest
from APP.service import get_chat_service

router = APIRouter(prefix="", tags=["reminder"])


def _to_detail(reminder) -> ReminderDetail:
    recurrence = None
    if reminder.recurrence is not None:
        recurrence = {
            "frequency": reminder.recurrence.frequency,
            "interval": reminder.recurrence.interval,
        }
    return ReminderDetail(
        id=reminder.id,
        thread_id=reminder.thread_id,
        title=reminder.title,
        message=reminder.message,
        trigger_at=reminder.trigger_at,
        timezone=reminder.timezone,
        kind=reminder.kind,
        recurrence=recurrence,
        status=reminder.status,
        created_at=reminder.created_at,
        updated_at=reminder.updated_at,
        fired_at=reminder.fired_at,
        last_fired_at=reminder.last_fired_at,
        cancelled_at=reminder.cancelled_at,
        delivery_error=reminder.delivery_error,
    )


@router.get("/reminders", response_model=list[ReminderDetail], summary="List reminders")
async def list_reminders(include_cancelled: bool = False) -> list[ReminderDetail]:
    service = get_chat_service()
    reminders = await service.list_reminders(include_cancelled=include_cancelled)
    reminders.sort(key=lambda item: item.trigger_at)
    return [_to_detail(item) for item in reminders]


@router.get("/reminders/{reminder_id}", response_model=ReminderDetail, summary="Get reminder details")
async def get_reminder(reminder_id: str) -> ReminderDetail:
    service = get_chat_service()
    reminder = await service.get_reminder(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail=f"Reminder not found: {reminder_id}")
    return _to_detail(reminder)


@router.post("/reminders/update", response_model=ReminderDetail, summary="Update reminder")
async def update_reminder(payload: ReminderUpdateRequest) -> ReminderDetail:
    service = get_chat_service()
    try:
        reminder = await service.update_reminder(
            payload.reminder_id,
            title=payload.title,
            message=payload.message,
            trigger_at=payload.trigger_at,
            timezone=payload.timezone,
            recurrence_frequency=payload.recurrence_frequency,
            recurrence_interval=payload.recurrence_interval,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Reminder not found: {payload.reminder_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_detail(reminder)


@router.post("/reminders/delete", response_model=ReminderDetail, summary="Delete reminder")
async def delete_reminder(payload: ReminderDeleteRequest) -> ReminderDetail:
    service = get_chat_service()
    try:
        reminder = await service.delete_reminder(payload.reminder_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Reminder not found: {payload.reminder_id}") from exc
    return _to_detail(reminder)
