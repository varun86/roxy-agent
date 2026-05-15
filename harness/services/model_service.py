from __future__ import annotations

from typing import Any

from harness.config.settings import HarnessConfig


class ModelService:
    def __init__(self, *, config: HarnessConfig) -> None:
        self._config = config

    def list_models(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for model in self._config.models:
            items.append(
                {
                    "name": model.name,
                    "display_name": model.display_name,
                    "provider": model.provider,
                    "supports_vision": model.supports_vision,
                    "default": model.name == self._config.default_model,
                }
            )
        return items
