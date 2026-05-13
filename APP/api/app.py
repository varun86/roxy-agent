from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from APP.dto import (
    ChatRequest,
    ChatResponse,
    ConversationCreateResponse,
    ConversationDetail,
    ConversationRenameRequest,
    ConversationSummary,
    ModelInfo,
    ReminderDetail,
    TraceInfo,
)
from APP.service import get_chat_service
from harness.models.types import AgentRunResult

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


router = APIRouter(prefix="", tags=["chat"])


def _sse_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _summary_payload(summary: object) -> dict[str, object]:
    return {
        "thread_id": getattr(summary, "thread_id"),
        "title": getattr(summary, "title"),
        "created_at": getattr(summary, "created_at"),
        "updated_at": getattr(summary, "updated_at"),
        "last_message_preview": getattr(summary, "last_message_preview"),
        "message_count": getattr(summary, "message_count"),
    }


@router.post("/chat", response_model=ChatResponse, summary="Run chat request")
async def chat(request: ChatRequest) -> ChatResponse:
    service = get_chat_service()
    try:
        result: AgentRunResult = await service.run_chat(
            request.message,
            request.model,
            thread_id=request.thread_id,
            messages=[item.model_dump() for item in (request.messages or [])],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"API Error: {str(exc)}") from exc

    return ChatResponse(
        text=result.text,
        trace=TraceInfo(
            steps=result.trace.steps,
            tool_calls=result.trace.tool_calls,
            errors=result.trace.errors,
            subagent_calls=result.trace.subagent_calls,
            subagent_errors=result.trace.subagent_errors,
        ),
        thread_id=result.thread_id,
    )


@router.post("/chat/stream", summary="Run chat request with SSE stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    service = get_chat_service()

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in service.run_chat_stream(
                request.message,
                request.model,
                thread_id=request.thread_id,
                messages=[item.model_dump() for item in (request.messages or [])],
            ):
                yield _sse_event(event)
                await asyncio.sleep(0)
        except ValueError as exc:
            yield _sse_event({"type": "error", "error": str(exc)})
        except Exception as exc:
            yield _sse_event({"type": "error", "error": f"API Error: {str(exc)}"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/models", response_model=list[ModelInfo], summary="List available models")
async def list_models() -> list[ModelInfo]:
    service = get_chat_service()
    return [ModelInfo(**item) for item in service.list_models()]


@router.get("/conversations", response_model=list[ConversationSummary], summary="List conversations")
async def list_conversations() -> list[ConversationSummary]:
    service = get_chat_service()
    return [ConversationSummary(**_summary_payload(item)) for item in service.list_conversations()]


@router.get(
    "/conversations/{thread_id}",
    response_model=ConversationDetail,
    summary="Get conversation details",
)
async def get_conversation(thread_id: str) -> ConversationDetail:
    service = get_chat_service()
    detail = service.get_conversation(thread_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {thread_id}")
    payload = {
        **_summary_payload(detail.summary),
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


@router.post(
    "/conversations/create",
    response_model=ConversationCreateResponse,
    summary="Create conversation",
)
async def create_conversation() -> ConversationCreateResponse:
    service = get_chat_service()
    summary = service.create_conversation()
    return ConversationCreateResponse(**_summary_payload(summary))


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
    return ConversationSummary(**_summary_payload(summary))


@router.post("/conversations/{thread_id}/delete", summary="Delete conversation")
async def delete_conversation(thread_id: str) -> dict:
    service = get_chat_service()
    try:
        service.delete_conversation(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "deleted", "thread_id": thread_id}


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


@router.get("/health", summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    service = get_chat_service()
    await service.start_reminders()
    try:
        yield
    finally:
        await service.stop_reminders()


def create_app() -> FastAPI:
    app = FastAPI(
        title="My Deer Flow API",
        description="Application API layer for roxy-flow business endpoints.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/swagger",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app
