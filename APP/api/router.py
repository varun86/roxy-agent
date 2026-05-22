from __future__ import annotations

from fastapi import APIRouter

from APP.api.chat.router import router as chat_router
from APP.api.conversation.router import router as conversation_router
from APP.api.mcp.router import router as mcp_router
from APP.api.model.router import router as model_router
from APP.api.plugins.router import router as plugins_router
from APP.api.reminder.router import router as reminder_router
from APP.api.system.router import router as system_router


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(chat_router)
    router.include_router(conversation_router)
    router.include_router(mcp_router)
    router.include_router(model_router)
    router.include_router(plugins_router)
    router.include_router(reminder_router)
    router.include_router(system_router)
    return router
