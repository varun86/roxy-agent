from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SubagentConfig:
    name: str
    description: str
    system_prompt: str
    tools: list[str] | None = None
    disallowed_tools: list[str] = field(default_factory=lambda: ["task"])
    model: str = "inherit"
    max_steps: int = 8
    timeout_seconds: int = 900
