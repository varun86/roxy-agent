from __future__ import annotations

from fastapi import APIRouter

from APP.dto import ModelInfo
from APP.service import get_chat_service

router = APIRouter(prefix="", tags=["model"])


@router.get("/models", response_model=list[ModelInfo], summary="List available models")
async def list_models() -> list[ModelInfo]:
    service = get_chat_service()
    return [ModelInfo(**item) for item in service.list_models()]
