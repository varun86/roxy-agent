from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from APP.plugins.dto import PluginActionRequest, PluginStatusResponse
from APP.service import get_chat_service

router = APIRouter(prefix="/plugins", tags=["plugins"])


def _payload_from_request(request: PluginActionRequest | None) -> dict[str, Any]:
    if request is None:
        return {}
    payload = dict(request.payload or {})
    if request.text is not None:
        payload["text"] = request.text
    return payload


def _raise_plugin_error(plugin_id: str, exc: Exception) -> None:
    try:
        status = get_chat_service().get_plugin_status(plugin_id)
        detail = status.get("last_error") or str(exc)
    except Exception:
        detail = str(exc)
    raise HTTPException(status_code=400, detail=detail) from exc


@router.get("/{plugin_id}/status", response_model=PluginStatusResponse)
async def plugin_status(plugin_id: str) -> PluginStatusResponse:
    try:
        return PluginStatusResponse(**get_chat_service().get_plugin_status(plugin_id))
    except Exception as exc:
        _raise_plugin_error(plugin_id, exc)


@router.post("/{plugin_id}/enable", response_model=PluginStatusResponse)
async def enable_plugin(plugin_id: str) -> PluginStatusResponse:
    try:
        return PluginStatusResponse(**(await get_chat_service().enable_plugin(plugin_id)))
    except Exception as exc:
        _raise_plugin_error(plugin_id, exc)


@router.post("/{plugin_id}/disable", response_model=PluginStatusResponse)
async def disable_plugin(plugin_id: str) -> PluginStatusResponse:
    try:
        return PluginStatusResponse(**get_chat_service().disable_plugin(plugin_id))
    except Exception as exc:
        _raise_plugin_error(plugin_id, exc)


@router.post("/{plugin_id}/test", response_model=PluginStatusResponse)
async def test_plugin(plugin_id: str, request: PluginActionRequest | None = None) -> PluginStatusResponse:
    try:
        return PluginStatusResponse(**(await get_chat_service().test_plugin(plugin_id, _payload_from_request(request))))
    except Exception as exc:
        _raise_plugin_error(plugin_id, exc)
