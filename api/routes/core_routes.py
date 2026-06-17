"""Core endpoints: health check, translate_in, translate_out."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Body

from domain.api_models import TranslateOutRequest, HealthResponse
from core.app_config import axon_service


router = APIRouter(tags=["core"])


@router.get("/health", response_model=HealthResponse)
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@router.post("/translate/in")
async def translate_in(payload: Any = Body(...)) -> dict[str, Any]:
    """Normalize input to object format."""
    return {"object": axon_service.from_any_to_object(payload)}


@router.post("/translate/out")
async def translate_out(req: TranslateOutRequest) -> dict[str, Any]:
    """Convert output to GCF envelope with token metrics."""
    # Assume target_model can be passed in the request (e.g., as a header or query param)
    # or defaults to gpt-4o for token estimation consistency.
    target_model = getattr(req, 'target_model', 'gpt-4o')
    return axon_service.convert_output(req.data, session_id=req.session_id, model=target_model)
