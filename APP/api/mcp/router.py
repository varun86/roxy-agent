from __future__ import annotations

from fastapi import APIRouter

from APP.dto import McpConfigResponse, McpConfigUpdateRequest
from APP.service import get_chat_service

router = APIRouter(prefix="", tags=["mcp"])


@router.get("/mcp/config", response_model=McpConfigResponse, summary="Get MCP configuration")
async def get_mcp_config() -> McpConfigResponse:
    service = get_chat_service()
    return McpConfigResponse(**service.get_mcp_config())


@router.post("/mcp/config", response_model=McpConfigResponse, summary="Update MCP configuration")
async def update_mcp_config(request: McpConfigUpdateRequest) -> McpConfigResponse:
    service = get_chat_service()
    return McpConfigResponse(**service.update_mcp_config({name: item.model_dump() for name, item in request.mcp_servers.items()}))
