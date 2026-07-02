"""Request/response models for Axon Bridge API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TranslateOutRequest(BaseModel):
    """Request to convert output to Axon envelope."""
    data: Any
    session_id: str | None = None


class ProcessRequest(BaseModel):
    """Request to process payload through handler."""
    inbound: Any
    handler: str = Field(default="echo", description="One of: echo, active_items, graph_processor")
    session_id: str | None = None
    target_model: str | None = Field(default=None, description="Optional target LLM (e.g. gpt-4o)")


class UpstreamProxyRequest(BaseModel):
    """Request to forward to upstream API."""
    upstream_url: str
    method: str = Field(default="POST", description="HTTP method")
    headers: dict[str, str] | None = None
    data: Any = None
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    session_id: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str


class SessionDeleteResponse(BaseModel):
    """Session deletion response."""
    status: str
    session_id: str


class SecurityConfigResponse(BaseModel):
    """Security configuration view."""
    require_api_key: bool
    allow_all_domains: bool
    allowed_domains: list[str]
    has_api_key_set: bool
