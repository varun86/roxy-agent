from __future__ import annotations

from typing import Any

from APP.service.runtime.service import AppRuntimeService


class ConversationService:
    def __init__(self, runtime: AppRuntimeService) -> None:
        self.runtime = runtime

    def create_conversation(self, thread_id: str | None = None) -> Any:
        resolved_thread_id = self.runtime.resolve_or_create_thread_id(thread_id)
        thread_paths = self.runtime.thread_runtime.ensure_dirs(self.runtime.thread_runtime.resolve(resolved_thread_id))
        detail = self.runtime.conversation_store.ensure_conversation(
            resolved_thread_id,
            conversation_path=thread_paths.conversation_file,
            messages_path=thread_paths.messages_file,
        )
        return detail.summary

    def list_conversations(self) -> list[Any]:
        return self.runtime.conversation_store.list_conversations(self.runtime.thread_runtime.sandbox_root / "threads")

    def get_conversation(self, thread_id: str) -> Any | None:
        resolved_thread_id = self.runtime.normalize_thread_id(thread_id)
        if not resolved_thread_id:
            return None
        thread_paths = self.runtime.thread_runtime.resolve(resolved_thread_id)
        return self.runtime.conversation_store.load_conversation(
            resolved_thread_id,
            conversation_path=thread_paths.conversation_file,
            messages_path=thread_paths.messages_file,
        )

    def rename_conversation(self, thread_id: str, title: str) -> Any:
        resolved_thread_id = self.runtime.normalize_thread_id(thread_id)
        if not resolved_thread_id:
            raise ValueError("thread_id is required")
        thread_paths = self.runtime.thread_runtime.ensure_dirs(self.runtime.thread_runtime.resolve(resolved_thread_id))
        return self.runtime.conversation_store.rename_conversation(
            resolved_thread_id,
            title,
            conversation_path=thread_paths.conversation_file,
            messages_path=thread_paths.messages_file,
        )

    def delete_conversation(self, thread_id: str) -> None:
        self.runtime.delete_thread_root(thread_id)
