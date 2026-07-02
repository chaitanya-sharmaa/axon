"""Memory endpoints: session tracking and cleanup."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from core.app_config import axon_service, memory_store

router = APIRouter(tags=["memory"])


@router.delete("/session/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Clear session data and dedup cache."""
    await memory_store.delete_session(session_id)
    axon_service.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    """List all active sessions with metadata."""
    # Better to delegate this to the memory_store service
    sessions = await memory_store.list_all_sessions()
    return {
        "sessions": sessions,
        "count": len(sessions),
    }


@router.get("/session/{session_id}")
async def get_session_info(session_id: str, limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    """Get session metadata and event history."""
    if not await memory_store.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    symbols = await memory_store.get_session_symbols(session_id)
    history = await memory_store.get_session_history(session_id, limit=limit)

    return {
        "session_id": session_id,
        "symbols_cached": len(symbols),
        "history_events": len(history),
        "symbols": symbols[:20],  # First 20 for preview
        "recent_events": history,
    }


@router.delete("/cleanup")
async def cleanup_memory(days: int = Query(default=7, ge=1)) -> dict[str, Any]:
    """Delete sessions older than specified days."""
    deleted = await memory_store.cleanup_old_sessions(days=days)
    return {
        "deleted_sessions": deleted,
        "cutoff_days": days,
    }
