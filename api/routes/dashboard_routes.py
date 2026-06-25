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


