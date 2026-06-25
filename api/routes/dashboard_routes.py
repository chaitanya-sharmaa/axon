import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from core.settings import settings

router = APIRouter(tags=["dashboard"])

# Path to the built React Vite app
DASHBOARD_BUILD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dashboard", "dist")


# ── Admin Auth ────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)

def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    """Enforce admin_api_key if one is configured. If none is set, allow all (dev mode)."""
    if settings.admin_api_key:
        if creds is None or creds.credentials != settings.admin_api_key:
            raise HTTPException(status_code=403, detail="Invalid or missing admin API key. Set AXON_ADMIN_API_KEY in .env or pass as Bearer token.")


# ── Dashboard UI ──────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard():
    """Serve the real-time Axon metrics dashboard (React/Vite app)."""
    index_path = os.path.join(DASHBOARD_BUILD_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Dashboard build not found. Please run 'cd dashboard && npm run build'"}


# ── Feature Flags ─────────────────────────────────────────────────────────────

class FeatureFlagsUpdate(BaseModel):
    enable_semantic_routing: bool | None = None
    enable_exact_match_cache: bool | None = None
    enable_tool_compression: bool | None = None
    enable_rag_context: bool | None = None


@router.get("/admin/features", dependencies=[Depends(require_admin)])
def get_features():
    """Get the current state of feature flags."""
    return {
        "enable_semantic_routing": settings.enable_semantic_routing,
        "enable_exact_match_cache": settings.enable_exact_match_cache,
        "enable_tool_compression": settings.enable_tool_compression,
        "enable_rag_context": settings.enable_rag_context,
    }


@router.post("/admin/features", dependencies=[Depends(require_admin)])
def update_features(flags: FeatureFlagsUpdate):
    """Dynamically update feature flags at runtime."""
    if flags.enable_semantic_routing is not None:
        settings.enable_semantic_routing = flags.enable_semantic_routing
    if flags.enable_exact_match_cache is not None:
        settings.enable_exact_match_cache = flags.enable_exact_match_cache
    if flags.enable_tool_compression is not None:
        settings.enable_tool_compression = flags.enable_tool_compression
    if flags.enable_rag_context is not None:
        settings.enable_rag_context = flags.enable_rag_context
    return get_features()


# ── Live Firehose ─────────────────────────────────────────────────────────────

from services.request_logger import request_logger


@router.get("/admin/requests", dependencies=[Depends(require_admin)])
def get_requests():
    """Get the live request firehose (last 100 requests)."""
    return request_logger.get_logs(limit=100)


# ── Cache Explorer ────────────────────────────────────────────────────────────

from services.semantic_cache import semantic_cache


@router.get("/admin/cache", dependencies=[Depends(require_admin)])
def get_cache_entries():
    """Get semantic cache entries — uses thread-safe snapshot method."""
    return semantic_cache.get_all_entries()


# ── Security Events ───────────────────────────────────────────────────────────

from services.event_logger import event_logger


@router.get("/admin/events/firewall", dependencies=[Depends(require_admin)])
def get_firewall_events():
    """Get prompt injection / jailbreak events."""
    return event_logger.get_firewall_events(limit=100)


@router.get("/admin/events/pii", dependencies=[Depends(require_admin)])
def get_pii_events():
    """Get PII redaction events and type counts."""
    return {
        "events": event_logger.get_pii_events(limit=100),
        "counts": event_logger.pii_type_counts(),
    }


@router.get("/admin/events/entropy", dependencies=[Depends(require_admin)])
def get_entropy_events():
    """Get Shannon entropy / hallucination guard events."""
    return event_logger.get_entropy_events(limit=100)


# ── Health ────────────────────────────────────────────────────────────────────

import time as _time
import os as _os
_start_time = _time.time()


@router.get("/admin/health")
def get_health():
    """System health and uptime."""
    logs = request_logger.get_logs(limit=500)
    uptime_s = _time.time() - _start_time
    req_per_min = len([l for l in logs if _time.time() - l["timestamp"] < 60])
    errors = len([l for l in logs if l["status_code"] >= 400])
    total_cost = sum(l.get("cost", 0) for l in logs)
    return {
        "status": "ok",
        "version": "0.3.0",
        "uptime_seconds": int(uptime_s),
        "uptime_human": f"{int(uptime_s // 3600)}h {int((uptime_s % 3600) // 60)}m",
        "requests_last_minute": req_per_min,
        "total_requests": len(logs),
        "error_count": errors,
        "total_cost_usd": round(total_cost, 6),
    }


# ── Tenants ───────────────────────────────────────────────────────────────────

from core.app_config import memory_store


@router.get("/admin/tenants", dependencies=[Depends(require_admin)])
async def get_tenants():
    """List all tenants with quota and spend info."""
    if not memory_store or not hasattr(memory_store, "list_all_tenants"):
        return []
    try:
        return await memory_store.list_all_tenants()
    except Exception:
        return []


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/admin/sessions", dependencies=[Depends(require_admin)])
async def get_sessions():
    """List active memory sessions."""
    if not memory_store or not hasattr(memory_store, "list_all_sessions"):
        return []
    try:
        return await memory_store.list_all_sessions()
    except Exception:
        return []



