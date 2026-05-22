from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


TransportType = Literal["stdio", "sse", "http"]
OAuthGrantType = Literal["client_credentials", "refresh_token"]


@dataclass(slots=True)
class McpOAuthConfig:
    enabled: bool = True
    token_url: str = ""
    grant_type: OAuthGrantType = "client_credentials"
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    scope: str | None = None
    audience: str | None = None
    token_field: str = "access_token"
    token_type_field: str = "token_type"
    expires_in_field: str = "expires_in"
    default_token_type: str = "Bearer"
    refresh_skew_seconds: int = 60
    extra_token_params: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "McpOAuthConfig":
        return cls(
            enabled=bool(data.get("enabled", True)),
            token_url=str(data.get("token_url", "")),
            grant_type=str(data.get("grant_type", "client_credentials")),  # type: ignore[arg-type]
            client_id=_optional_str(data.get("client_id")),
            client_secret=_optional_str(data.get("client_secret")),
            refresh_token=_optional_str(data.get("refresh_token")),
            scope=_optional_str(data.get("scope")),
            audience=_optional_str(data.get("audience")),
            token_field=str(data.get("token_field", "access_token")),
            token_type_field=str(data.get("token_type_field", "token_type")),
            expires_in_field=str(data.get("expires_in_field", "expires_in")),
            default_token_type=str(data.get("default_token_type", "Bearer")),
            refresh_skew_seconds=int(data.get("refresh_skew_seconds", 60)),
            extra_token_params=_string_dict(data.get("extra_token_params")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "token_url": self.token_url,
            "grant_type": self.grant_type,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "scope": self.scope,
            "audience": self.audience,
            "token_field": self.token_field,
            "token_type_field": self.token_type_field,
            "expires_in_field": self.expires_in_field,
            "default_token_type": self.default_token_type,
            "refresh_skew_seconds": self.refresh_skew_seconds,
            "extra_token_params": dict(self.extra_token_params),
        }


@dataclass(slots=True)
class McpServerConfig:
    enabled: bool = True
    type: TransportType = "stdio"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    oauth: McpOAuthConfig | None = None
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "McpServerConfig":
        oauth_raw = data.get("oauth")
        return cls(
            enabled=bool(data.get("enabled", True)),
            type=str(data.get("type", "stdio")),  # type: ignore[arg-type]
            command=_optional_str(data.get("command")),
            args=[str(item) for item in data.get("args", [])] if isinstance(data.get("args"), list) else [],
            env=_string_dict(data.get("env")),
            url=_optional_str(data.get("url")),
            headers=_string_dict(data.get("headers")),
            oauth=McpOAuthConfig.from_dict(oauth_raw) if isinstance(oauth_raw, dict) else None,
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "enabled": self.enabled,
            "type": self.type,
            "command": self.command,
            "args": list(self.args),
            "env": dict(self.env),
            "url": self.url,
            "headers": dict(self.headers),
            "description": self.description,
        }
        if self.oauth is not None:
            payload["oauth"] = self.oauth.to_dict()
        return payload


@dataclass(slots=True)
class SkillStateConfig:
    enabled: bool = True

    @classmethod
    def from_value(cls, value: Any) -> "SkillStateConfig":
        if isinstance(value, dict):
            return cls(enabled=bool(value.get("enabled", True)))
        return cls(enabled=bool(value))

    def to_dict(self) -> dict[str, bool]:
        return {"enabled": self.enabled}


@dataclass(slots=True)
class PluginStateConfig:
    enabled: bool = False
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: Any) -> "PluginStateConfig":
        if isinstance(value, dict):
            raw_config = value.get("config", {})
            return cls(
                enabled=bool(value.get("enabled", False)),
                config=dict(raw_config) if isinstance(raw_config, dict) else {},
            )
        return cls(enabled=bool(value), config={})

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "config": dict(self.config)}


@dataclass(slots=True)
class ExtensionsConfig:
    mcp_servers: dict[str, McpServerConfig] = field(default_factory=dict)
    skills: dict[str, SkillStateConfig] = field(default_factory=dict)
    plugins: dict[str, PluginStateConfig] = field(default_factory=dict)

    @classmethod
    def resolve_config_path(cls, config_path: str | None = None) -> Path | None:
        if config_path:
            path = Path(config_path)
            if not path.exists():
                raise FileNotFoundError(f"extensions config not found: {path}")
            return path

        env_path = os.getenv("HARNESS_EXTENSIONS_CONFIG_PATH", "").strip()
        if env_path:
            path = Path(env_path)
            if not path.exists():
                raise FileNotFoundError(f"extensions config not found: {path}")
            return path

        candidates = [
            Path.cwd() / "extensions_config.json",
            Path.cwd().parent / "extensions_config.json",
            Path.cwd() / "mcp_config.json",
            Path.cwd().parent / "mcp_config.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @classmethod
    def from_file(cls, config_path: str | None = None) -> "ExtensionsConfig":
        resolved_path = cls.resolve_config_path(config_path)
        if resolved_path is None:
            return cls(mcp_servers={}, skills={})

        with resolved_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            raise ValueError("extensions config must be a JSON object")

        resolved = cls.resolve_env_variables(raw)

        mcp_items = resolved.get("mcpServers", {})
        mcp_servers: dict[str, McpServerConfig] = {}
        if isinstance(mcp_items, dict):
            for name, value in mcp_items.items():
                if isinstance(value, dict):
                    mcp_servers[name] = McpServerConfig.from_dict(value)

        skill_items = resolved.get("skills", {})
        skills: dict[str, SkillStateConfig] = {}
        if isinstance(skill_items, dict):
            for name, value in skill_items.items():
                skills[name] = SkillStateConfig.from_value(value)

        plugin_items = resolved.get("plugins", {})
        plugins: dict[str, PluginStateConfig] = {}
        if isinstance(plugin_items, dict):
            for name, value in plugin_items.items():
                plugins[name] = PluginStateConfig.from_value(value)
        return cls(mcp_servers=mcp_servers, skills=skills, plugins=plugins)

    @classmethod
    def resolve_env_variables(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value.startswith("$"):
                return os.getenv(value[1:], "")
            return value
        if isinstance(value, dict):
            return {key: cls.resolve_env_variables(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls.resolve_env_variables(item) for item in value]
        return value

    def get_enabled_mcp_servers(self) -> dict[str, McpServerConfig]:
        return {name: config for name, config in self.mcp_servers.items() if config.enabled}

    def is_skill_enabled(self, skill_name: str, skill_category: str) -> bool:
        entry = self.skills.get(skill_name)
        if entry is None:
            return skill_category in ("public", "custom")
        return entry.enabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "mcpServers": {name: server.to_dict() for name, server in self.mcp_servers.items()},
            "skills": {name: skill.to_dict() for name, skill in self.skills.items()},
            "plugins": {name: plugin.to_dict() for name, plugin in self.plugins.items()},
        }


_extensions_config: ExtensionsConfig | None = None


def get_extensions_config(config_path: str | None = None) -> ExtensionsConfig:
    global _extensions_config
    if _extensions_config is None:
        _extensions_config = ExtensionsConfig.from_file(config_path)
    return _extensions_config


def reload_extensions_config(config_path: str | None = None) -> ExtensionsConfig:
    global _extensions_config
    _extensions_config = ExtensionsConfig.from_file(config_path)
    return _extensions_config


def reset_extensions_config() -> None:
    global _extensions_config
    _extensions_config = None


def set_extensions_config(config: ExtensionsConfig) -> None:
    global _extensions_config
    _extensions_config = config


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
