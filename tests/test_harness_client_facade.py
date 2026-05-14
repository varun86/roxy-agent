from __future__ import annotations

import json

from harness.client import HarnessClient


def test_harness_client_facade_forwards_mcp_and_model_methods(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='tmp'\nversion='0.0.0'\n", encoding="utf-8")
    (tmp_path / "harness").mkdir(parents=True, exist_ok=True)
    (tmp_path / "extensions_config.json").write_text(
        json.dumps({"mcpServers": {}, "skills": {}}),
        encoding="utf-8",
    )

    client = HarnessClient(project_root=tmp_path)

    assert "mcp_servers" in client.get_mcp_config()
    assert isinstance(client.list_models(), list)
