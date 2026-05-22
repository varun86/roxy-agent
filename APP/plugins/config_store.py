from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_extensions_payload(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("extensions config must be a JSON object")
    return raw


def write_extensions_payload(config_path: Path, payload: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_plugin_enabled(config_path: Path, plugin_id: str, enabled: bool) -> dict[str, Any]:
    payload = read_extensions_payload(config_path)
    plugins = payload.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        plugins = {}
        payload["plugins"] = plugins
    entry = plugins.setdefault(plugin_id, {})
    if not isinstance(entry, dict):
        entry = {}
        plugins[plugin_id] = entry
    entry["enabled"] = enabled
    entry.setdefault("config", {})
    write_extensions_payload(config_path, payload)
    return entry
