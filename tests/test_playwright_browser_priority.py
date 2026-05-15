from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from harness.client import HarnessClient


def test_harness_client_skips_local_browser_tools_when_playwright_mcp_enabled(tmp_path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='tmp'\nversion='0.0.0'\n", encoding="utf-8")
    (tmp_path / "harness").mkdir(parents=True, exist_ok=True)
    (tmp_path / "extensions_config.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "playwright": {
                        "enabled": True,
                        "type": "stdio",
                        "command": "npx",
                        "args": ["-y", "@playwright/mcp"],
                    }
                },
                "skills": {},
            }
        ),
        encoding="utf-8",
    )

    client = HarnessClient(project_root=tmp_path)
    monkeypatch.setenv("HARNESS_API_KEY", "test-key")

    with patch("harness.services.mcp_service.get_cached_mcp_tools", return_value=[]):
        agent = client._build_agent()

    tool_names = {item["function"]["name"] for item in agent.tool_schemas}
    assert "browser_search" not in tool_names
    assert "browser_open" not in tool_names
