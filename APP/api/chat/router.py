from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from APP.dto import ChatRequest, ChatResponse, TraceInfo
from APP.service import get_chat_service
from harness.models.types import AgentRunResult

router = APIRouter(prefix="", tags=["chat"])


def _sse_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
