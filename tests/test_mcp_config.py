from __future__ import annotations

import json

from harness.config.extensions_config import ExtensionsConfig, McpServerConfig
from harness.mcp.client import build_server_params, build_servers_config


def test_extensions_config_loads_mcp_servers_and_skills(tmp_path, monkeypatch):
    config_path = tmp_path / "extensions_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "github": {
                        "enabled": True,
                        "type": "stdio",
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-github"],
                        "env": {"GITHUB_TOKEN": "$TEST_GITHUB_TOKEN"},
                        "description": "GitHub MCP",
                    },
                    "playwright": {
                        "enabled": False,
                        "type": "http",
                        "url": "https://example.com/mcp",
                        "headers": {"Authorization": "$TEST_AUTH"},
                    },
                },
                "skills": {"example": {"enabled": False}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_GITHUB_TOKEN", "gh-token")
    monkeypatch.setenv("TEST_AUTH", "Bearer abc")

    config = ExtensionsConfig.from_file(str(config_path))

    assert config.mcp_servers["github"].env["GITHUB_TOKEN"] == "gh-token"
    assert config.mcp_servers["playwright"].headers["Authorization"] == "Bearer abc"
    assert config.skills["example"].enabled is False
    assert list(config.get_enabled_mcp_servers()) == ["github"]


def test_build_server_params_supports_stdio_http_and_sse():
    stdio_params = build_server_params(
        "github",
        McpServerConfig(type="stdio", command="npx", args=["-y", "@modelcontextprotocol/server-github"], env={"GITHUB_TOKEN": "x"}),
    )
    http_params = build_server_params(
        "playwright",
        McpServerConfig(type="http", url="https://example.com/mcp", headers={"Authorization": "Bearer x"}),
    )
    sse_params = build_server_params(
        "events",
        McpServerConfig(type="sse", url="https://example.com/sse"),
    )

    assert stdio_params == {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_TOKEN": "x"},
    }
    assert http_params == {
        "transport": "http",
        "url": "https://example.com/mcp",
        "headers": {"Authorization": "Bearer x"},
    }
    assert sse_params == {"transport": "sse", "url": "https://example.com/sse"}


def test_build_servers_config_filters_disabled_servers():
    config = ExtensionsConfig(
        mcp_servers={
            "github": McpServerConfig(enabled=True, type="stdio", command="npx"),
            "playwright": McpServerConfig(enabled=False, type="stdio", command="npx"),
        },
        skills={},
    )

    servers = build_servers_config(config)

    assert list(servers) == ["github"]
