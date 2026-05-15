from __future__ import annotations


def summary_payload(summary: object) -> dict[str, object]:
    return {
        "thread_id": getattr(summary, "thread_id"),
        "title": getattr(summary, "title"),
        "created_at": getattr(summary, "created_at"),
        "updated_at": getattr(summary, "updated_at"),
        "last_message_preview": getattr(summary, "last_message_preview"),
        "message_count": getattr(summary, "message_count"),
    }
