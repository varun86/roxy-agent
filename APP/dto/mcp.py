from __future__ import annotations

from pydantic import BaseModel, Field


class McpOAuthConfigPayload(BaseModel):
    enabled: bool = True
    token_url: str = ""
    grant_type: str = "client_credentials"
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
    extra_token_params: dict[str, str] = Field(default_factory=dict)


class McpServerConfigPayload(BaseModel):
    enabled: bool = True
    type: str = "stdio"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    oauth: McpOAuthConfigPayload | None = None
    description: str = ""


class McpConfigResponse(BaseModel):
    mcp_servers: dict[str, McpServerConfigPayload] = Field(default_factory=dict)


class McpConfigUpdateRequest(BaseModel):
    mcp_servers: dict[str, McpServerConfigPayload] = Field(default_factory=dict)
