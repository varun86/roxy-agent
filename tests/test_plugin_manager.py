from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from APP.plugins.base import PluginHostContext, PluginStatus
from APP.plugins.manager import AppPluginManager
from APP.plugins.registry import AssistantMessageContext, PluginCapabilityRegistry, RealtimePromptContract


class DemoPlugin:
    plugin_id = "demo_plugin"
    plugin_name = "Demo Plugin"
    plugin_version = "0.1.0"
    priority = 10

    def __init__(self) -> None:
        self.enabled = False
        self.hook_calls: list[AssistantMessageContext] = []

    def initialize(self, register: PluginCapabilityRegistry, host: PluginHostContext) -> None:
        self.enabled = host.enabled
        register.register_realtime_prompt_contract(
            RealtimePromptContract(
                plugin_id=self.plugin_id,
                prompt_text="<demo>append <demo_payload>...</demo_payload></demo>",
                parse_payload=self.parse_payload,
                is_enabled=lambda: self.enabled,
            )
        )
        register.register_assistant_message_hook(self.plugin_id, self.after_assistant_message)
        register.register_management(self.plugin_id, self)

    def shutdown(self) -> None:
        return None

    def status(self) -> PluginStatus:
        return PluginStatus(plugin_id=self.plugin_id, enabled=self.enabled)

    async def enable(self) -> PluginStatus:
        self.enabled = True
        return self.status()

    def disable(self) -> PluginStatus:
        self.enabled = False
        return self.status()

    async def test(self, payload: dict[str, Any] | None = None) -> PluginStatus:
        self.enabled = True
        return self.status()

    async def after_assistant_message(self, context: AssistantMessageContext) -> None:
        self.hook_calls.append(context)

    @staticmethod
    def parse_payload(text: str) -> tuple[str, str | None]:
        marker = "<demo_payload>"
        end_marker = "</demo_payload>"
        if marker not in text or end_marker not in text:
            return text, None
        before, rest = text.split(marker, 1)
        payload, after = rest.split(end_marker, 1)
        return (before + after).strip(), payload.strip()


class FailingHookPlugin(DemoPlugin):
    plugin_id = "failing_plugin"

    async def after_assistant_message(self, context: AssistantMessageContext) -> None:
        raise RuntimeError("hook failed")


def test_plugin_manager_loads_enabled_state_and_extracts_payload(tmp_path: Path):
    (tmp_path / "extensions_config.json").write_text(
        '{"plugins":{"demo_plugin":{"enabled":true,"config":{}}}}',
        encoding="utf-8",
    )
    manager = AppPluginManager(project_root=tmp_path, plugin_classes=[DemoPlugin])

    assert manager.get_realtime_prompt_text() == "<demo>append <demo_payload>...</demo_payload></demo>"
    visible, payloads = manager.extract_control_payloads("hello <demo_payload>spoken</demo_payload>")

    assert visible == "hello"
    assert payloads == {"demo_plugin": "spoken"}


@pytest.mark.asyncio
async def test_plugin_manager_persists_enable_disable(tmp_path: Path):
    (tmp_path / "extensions_config.json").write_text(
        '{"plugins":{"demo_plugin":{"enabled":false,"config":{}}}}',
        encoding="utf-8",
    )
    manager = AppPluginManager(project_root=tmp_path, plugin_classes=[DemoPlugin])

    assert (await manager.enable("demo-plugin")).enabled is True
    assert '"enabled": true' in (tmp_path / "extensions_config.json").read_text(encoding="utf-8")

    assert manager.disable("demo_plugin").enabled is False
    assert '"enabled": false' in (tmp_path / "extensions_config.json").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_plugin_manager_hook_failure_does_not_break_dispatch(tmp_path: Path):
    (tmp_path / "extensions_config.json").write_text(
        '{"plugins":{"demo_plugin":{"enabled":true,"config":{}},"failing_plugin":{"enabled":true,"config":{}}}}',
        encoding="utf-8",
    )
    manager = AppPluginManager(project_root=tmp_path, plugin_classes=[FailingHookPlugin, DemoPlugin])

    await manager.after_assistant_message(
        visible_text="hello",
        control_payloads={"demo_plugin": "spoken"},
        thread_id="thread-a",
        trace={},
    )
    demo = manager.get_plugin("demo_plugin")

    assert demo.hook_calls[0].control_payload == "spoken"
