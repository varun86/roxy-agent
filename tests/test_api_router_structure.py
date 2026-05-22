from __future__ import annotations

from APP.api.router import build_api_router


def test_build_api_router_includes_all_expected_routes():
    router = build_api_router()
    paths = {route.path for route in router.routes}

    assert "/chat" in paths
    assert "/chat/stream" in paths
    assert "/models" in paths
    assert "/mcp/config" in paths
    assert "/conversations" in paths
    assert "/conversations/{thread_id}" in paths
    assert "/reminders" in paths
    assert "/reminders/{reminder_id}" in paths
    assert "/reminders/update" in paths
    assert "/reminders/delete" in paths
    assert "/plugins/{plugin_id}/status" in paths
    assert "/plugins/{plugin_id}/enable" in paths
    assert "/plugins/{plugin_id}/disable" in paths
    assert "/plugins/{plugin_id}/test" in paths
    assert "/health" in paths
