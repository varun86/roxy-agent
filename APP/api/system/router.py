from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="", tags=["system"])


@router.get("/health", summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok"}
