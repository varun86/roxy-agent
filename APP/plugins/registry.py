from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from APP.plugins.base import PluginStatus


@dataclass(frozen=True, slots=True)
class AssistantMessageContext:
    visible_text: str
    control_payload: Any | None
    thread_id: str
    trace: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RealtimePromptContract:
    plugin_id: str
    prompt_text: str
    parse_payload: Callable[[str], tuple[str, Any | None]]
    is_enabled: Callable[[], bool]


class PluginManagementHandler(Protocol):
    def status(self) -> PluginStatus:
        ...

    async def enable(self) -> PluginStatus:
        ...

    def disable(self) -> PluginStatus:
        ...

    async def test(self, payload: dict[str, Any] | None = None) -> PluginStatus:
        ...


AssistantMessageHook = Callable[[AssistantMessageContext], Awaitable[None]]


class PluginCapabilityRegistry:
    def __init__(self) -> None:
        self._assistant_message_hooks: dict[str, AssistantMessageHook] = {}
        self._realtime_prompt_contracts: dict[str, RealtimePromptContract] = {}
        self._management_handlers: dict[str, PluginManagementHandler] = {}

    @property
    def assistant_message_hooks(self) -> dict[str, AssistantMessageHook]:
        return dict(self._assistant_message_hooks)

    @property
    def realtime_prompt_contracts(self) -> dict[str, RealtimePromptContract]:
        return dict(self._realtime_prompt_contracts)

    @property
    def management_handlers(self) -> dict[str, PluginManagementHandler]:
        return dict(self._management_handlers)

    def register_assistant_message_hook(self, plugin_id: str, hook: AssistantMessageHook) -> None:
        self._assistant_message_hooks[plugin_id] = hook

    def register_realtime_prompt_contract(self, contract: RealtimePromptContract) -> None:
        self._realtime_prompt_contracts[contract.plugin_id] = contract

    def register_management(self, plugin_id: str, handler: PluginManagementHandler) -> None:
        self._management_handlers[plugin_id] = handler
