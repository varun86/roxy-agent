from __future__ import annotations

from harness.scheduler import Reminder, ReminderScheduler


class ReminderService:
    def __init__(self, reminders: ReminderScheduler) -> None:
        self._reminders = reminders

    async def start(self) -> None:
        await self._reminders.start()

    async def stop(self) -> None:
        await self._reminders.stop()

    async def get_reminder(self, reminder_id: str) -> Reminder | None:
        return await self._reminders.get_reminder(reminder_id)
