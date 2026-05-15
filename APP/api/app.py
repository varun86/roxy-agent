from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from APP.api.router import build_api_router
from APP.service import get_chat_service

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


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

    app.include_router(build_api_router())
    return app
