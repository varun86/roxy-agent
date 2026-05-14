from __future__ import annotations

from pydantic import BaseModel, Field

from APP.dto.chat import TraceInfo


class ToolCallEventInfo(BaseModel):
    call_id: str
    tool_name: str
    arguments: dict[str, object]
    output: str
    is_error: bool = False


class ConversationMessage(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    is_error: bool = False
    tool_events: list[ToolCallEventInfo] = Field(default_factory=list)
    trace: TraceInfo | None = None


class ConversationSummary(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    last_message_preview: str
    message_count: int


class ConversationDetail(ConversationSummary):
    messages: list[ConversationMessage]


class ConversationCreateResponse(ConversationSummary):
    pass


class ConversationRenameRequest(BaseModel):
    title: str
