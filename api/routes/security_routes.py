"""Security endpoints: domain allowlist and API key management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from domain.api_models import SecurityConfigResponse
from core.app_config import security_config


router = APIRouter(tags=["security"])


@router.get("/config", response_model=SecurityConfigResponse)
async def get_security_config() -> dict[str, Any]:
    """Get current security configuration (excluding sensitive keys)."""
    return security_config.to_dict()


@router.post("/domain/allow")
async def add_allowed_domain(domain: str = Query(...)) -> dict[str, Any]:
    """Add domain to proxy allowlist."""
    security_config.add_domain(domain)
    return {
        "domain": domain,
        "action": "added",
        "allowed_domains": security_config.allowed_domains,
    }


@router.delete("/domain")
async def remove_allowed_domain(domain: str = Query(...)) -> dict[str, Any]:
    """Remove domain from proxy allowlist."""
    security_config.remove_domain(domain)
    return {
        "domain": domain,
        "action": "removed",
        "allowed_domains": security_config.allowed_domains,
    }


@router.post("/require-api-key")
async def set_api_key_requirement(required: bool = Query(default=True)) -> dict[str, Any]:
    """Enable or disable API key requirement for proxy endpoint."""
    security_config.require_api_key = required
    return {
        "require_api_key": required,
        "status": "updated",
    }


@router.post("/allow-all-domains")
async def set_allow_all_domains(allow: bool = Query(default=False)) -> dict[str, Any]:
    """Enable or disable allowing all domains (WARNING: security risk)."""
    security_config.allow_all_domains = allow
    return {
        "allow_all_domains": allow,
        "status": "updated",
        "warning": "All domains allowed - disable before production!" if allow else None,
    }



