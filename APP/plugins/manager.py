from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable, Type

from APP.plugins.base import PluginBase, PluginHostContext, PluginStatus
from APP.plugins.builtin import RoxyRealtimeTtsPlugin
from APP.plugins.config_store import update_plugin_enabled
from APP.plugins.registry import AssistantMessageContext, PluginCapabilityRegistry
from harness.config.extensions_config import ExtensionsConfig


class AppPluginManager:
    def __init__(
        self,
        *,
        project_root: Path,
        fallback_tts_line_generator: Callable[[str], Awaitable[str]] | None = None,
        plugin_classes: list[Type[PluginBase]] | None = None,
    ) -> None:
        self.project_root = project_root
        self.config_path = project_root / "extensions_config.json"
        self.plugin_data_root = project_root / "data" / "plugins"
        self._fallback_tts_line_generator = fallback_tts_line_generator
        self._plugin_classes = plugin_classes or [RoxyRealtimeTtsPlugin]
        self._registry = PluginCapabilityRegistry()
        self._plugins: dict[str, PluginBase] = {}
        self._load_plugins()

    def _load_plugins(self) -> None:
        config = ExtensionsConfig.from_file(str(self.config_path))
        self.plugin_data_root.mkdir(parents=True, exist_ok=True)
        instances: list[PluginBase] = []
        for cls in self._plugin_classes:
            instances.append(cls())
        for plugin in sorted(instances, key=lambda item: item.priority):
            state = config.plugins.get(plugin.plugin_id)
            plugin_root = self.plugin_data_root / plugin.plugin_id.replace("/", "_")
            plugin_root.mkdir(parents=True, exist_ok=True)
            host = PluginHostContext(
                project_root=self.project_root,
                config_path=self.config_path,
                plugin_root=plugin_root,
                enabled=bool(state.enabled) if state is not None else False,
                config=state.config if state is not None else {},
                fallback_tts_line_generator=self._fallback_tts_line_generator,
            )
            plugin.initialize(self._registry, host)
            self._plugins[plugin.plugin_id] = plugin

    def get_plugin(self, plugin_id: str) -> PluginBase | None:
        return self._plugins.get(self.normalize_plugin_id(plugin_id))

    def get_realtime_prompt_text(self) -> str | None:
        prompts = [
            contract.prompt_text
            for contract in self._registry.realtime_prompt_contracts.values()
            if contract.is_enabled()
        ]
        return "\n\n".join(prompts) if prompts else None

    def extract_control_payloads(self, text: str) -> tuple[str, dict[str, Any]]:
        visible_text = text
        payloads: dict[str, Any] = {}
        for plugin_id, contract in self._registry.realtime_prompt_contracts.items():
            if not contract.is_enabled():
                continue
            visible_text, payload = contract.parse_payload(visible_text)
            if payload is not None:
                payloads[plugin_id] = payload
        return visible_text, payloads

    async def after_assistant_message(
        self,
        *,
        visible_text: str,
        control_payloads: dict[str, Any],
        thread_id: str,
        trace: dict[str, Any],
    ) -> None:
        for plugin_id, hook in self._registry.assistant_message_hooks.items():
            try:
                await hook(
                    AssistantMessageContext(
                        visible_text=visible_text,
                        control_payload=control_payloads.get(plugin_id),
                        thread_id=thread_id,
                        trace=trace,
                    )
                )
            except Exception:
                continue

    def status(self, plugin_id: str) -> PluginStatus:
        normalized = self.normalize_plugin_id(plugin_id)
        handler = self._registry.management_handlers.get(normalized)
        if handler is None:
            raise KeyError(f"unknown plugin: {plugin_id}")
        return handler.status()

    async def enable(self, plugin_id: str) -> PluginStatus:
        normalized = self.normalize_plugin_id(plugin_id)
        handler = self._registry.management_handlers.get(normalized)
        if handler is None:
            raise KeyError(f"unknown plugin: {plugin_id}")
        try:
            status = await handler.enable()
        except Exception:
            update_plugin_enabled(self.config_path, normalized, False)
            raise
        update_plugin_enabled(self.config_path, normalized, True)
        return status

    def disable(self, plugin_id: str) -> PluginStatus:
        normalized = self.normalize_plugin_id(plugin_id)
        handler = self._registry.management_handlers.get(normalized)
        if handler is None:
            raise KeyError(f"unknown plugin: {plugin_id}")
        status = handler.disable()
        update_plugin_enabled(self.config_path, normalized, False)
        return status

    async def test(self, plugin_id: str, payload: dict[str, Any] | None = None) -> PluginStatus:
        normalized = self.normalize_plugin_id(plugin_id)
        handler = self._registry.management_handlers.get(normalized)
        if handler is None:
            raise KeyError(f"unknown plugin: {plugin_id}")
        status = await handler.test(payload or {})
        update_plugin_enabled(self.config_path, normalized, True)
        return status

    @staticmethod
    def normalize_plugin_id(plugin_id: str) -> str:
        return plugin_id.strip().replace("-", "_")
