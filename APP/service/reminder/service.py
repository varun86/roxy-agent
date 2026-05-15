from __future__ import annotations

from harness.tools.reminder import Reminder, ReminderScheduler


class ReminderService:
    def __init__(self, reminders: ReminderScheduler) -> None:
        self._reminders = reminders

    async def start(self) -> None:
        await self._reminders.start()

    async def stop(self) -> None:
        await self._reminders.stop()

    async def get_reminder(self, reminder_id: str) -> Reminder | None:
        return await self._reminders.get_reminder(reminder_id)

    async def list_reminders(self, *, include_cancelled: bool = False) -> list[Reminder]:
        return await self._reminders.list_reminders(include_cancelled=include_cancelled)

    async def update_reminder(
        self,
        reminder_id: str,
        *,
        title: str | None = None,
        message: str | None = None,
        trigger_at: str | None = None,
        timezone: str | None = None,
        recurrence_frequency: str | None = None,
        recurrence_interval: int | None = None,
    ) -> Reminder:
        return await self._reminders.update_reminder(
            reminder_id,
            title=title,
            message=message,
            trigger_at=trigger_at,
            timezone=timezone,
            recurrence_frequency=recurrence_frequency,
            recurrence_interval=recurrence_interval,
        )

    async def delete_reminder(self, reminder_id: str) -> Reminder:
        return await self._reminders.delete_reminder(reminder_id)
