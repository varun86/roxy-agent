from __future__ import annotations

from fastapi import APIRouter, HTTPException

from APP.api.common import summary_payload
from APP.dto import (
    ConversationCreateResponse,
    ConversationDetail,
    ConversationRenameRequest,
    ConversationSummary,
)
from APP.service import get_chat_service

router = APIRouter(prefix="", tags=["conversation"])


@router.get("/conversations", response_model=list[ConversationSummary], summary="List conversations")
async def list_conversations() -> list[ConversationSummary]:
    service = get_chat_service()
    return [ConversationSummary(**summary_payload(item)) for item in service.list_conversations()]


@router.get("/conversations/{thread_id}", response_model=ConversationDetail, summary="Get conversation details")
async def get_conversation(thread_id: str) -> ConversationDetail:
    service = get_chat_service()
    detail = service.get_conversation(thread_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {thread_id}")
    payload = {
        **summary_payload(detail.summary),
        "messages": [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "created_at": item.created_at,
                "is_error": item.is_error,
                "tool_events": [
                    {
                        "call_id": tool_event.call_id,
                        "tool_name": tool_event.tool_name,
                        "arguments": tool_event.arguments,
                        "output": tool_event.output,
                        "is_error": tool_event.is_error,
                    }
                    for tool_event in item.tool_events
                ],
                "trace": (
                    {
                        "steps": item.trace.steps,
                        "tool_calls": item.trace.tool_calls,
                        "errors": item.trace.errors,
                        "subagent_calls": item.trace.subagent_calls,
                        "subagent_errors": item.trace.subagent_errors,
                    }
                    if item.trace is not None
                    else None
                ),
            }
            for item in detail.messages
        ],
    }
    return ConversationDetail(**payload)


@router.post("/conversations/create", response_model=ConversationCreateResponse, summary="Create conversation")
async def create_conversation() -> ConversationCreateResponse:
    service = get_chat_service()
    summary = service.create_conversation()
    return ConversationCreateResponse(**summary_payload(summary))


@router.post(
    "/conversations/{thread_id}/rename",
    response_model=ConversationSummary,
    summary="Rename conversation",
)
async def rename_conversation(thread_id: str, request: ConversationRenameRequest) -> ConversationSummary:
    service = get_chat_service()
    try:
        summary = service.rename_conversation(thread_id, request.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ConversationSummary(**summary_payload(summary))


@router.post("/conversations/{thread_id}/delete", summary="Delete conversation")
async def delete_conversation(thread_id: str) -> dict[str, str]:
    service = get_chat_service()
    try:
        service.delete_conversation(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "deleted", "thread_id": thread_id}
