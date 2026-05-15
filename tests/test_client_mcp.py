from __future__ import annotations

import json

from harness.client import HarnessClient


def test_harness_client_updates_mcp_config_and_preserves_skills(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='tmp'\nversion='0.0.0'\n", encoding="utf-8")
    (tmp_path / "harness").mkdir(parents=True, exist_ok=True)
    (tmp_path / "extensions_config.json").write_text(
        json.dumps({"mcpServers": {}, "skills": {"example": {"enabled": False}}}),
        encoding="utf-8",
    )

    client = HarnessClient(project_root=tmp_path)
    result = client.update_mcp_config(
        {
            "github": {
                "enabled": True,
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "$GITHUB_TOKEN"},
                "description": "GitHub MCP server",
            }
        }
    )

    assert "github" in result["mcp_servers"]

    saved = json.loads((tmp_path / "extensions_config.json").read_text(encoding="utf-8"))
    assert saved["skills"]["example"]["enabled"] is False
    assert saved["mcpServers"]["github"]["command"] == "npx"
