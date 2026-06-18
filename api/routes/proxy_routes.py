"""Proxy endpoint: forward HTTP requests to upstream APIs with GCF response encoding."""

from __future__ import annotations

from typing import Any
import httpx
import json

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse

from domain.api_models import UpstreamProxyRequest
from core.app_config import axon_service, memory_store, security_config


router = APIRouter(tags=["proxy"])


@router.post("/upstream")
async def proxy_upstream(
    req: UpstreamProxyRequest,
    x_api_key: str | None = Header(None),
) -> JSONResponse:
    """Forward HTTP request to upstream URL with GCF response encoding.
    
    Security checks:
    - Validates domain against allowlist
    - Optionally requires API key in X-API-Key header
    
    Returns:
    - GCF compact format
    - JSON fallback
    - Upstream metadata (status, content-type)
    - Token savings metrics
    """
    # Security: Check domain allowlist
    if not security_config.is_domain_allowed(req.upstream_url):
        raise HTTPException(
            status_code=403,
            detail="Domain not permitted. Contact your administrator to add it to the allowlist.",
        )
    
    # Security: Check API key if required
    if not security_config.validate_api_key(x_api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key (X-API-Key header)",
        )
    
    method = req.method.upper().strip()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise HTTPException(status_code=400, detail=f"Unsupported method: {method}")

    # Execute upstream request
    async with httpx.AsyncClient(timeout=req.timeout_seconds, follow_redirects=False) as client:
        try:
            # Prepare data/json for httpx
            json_payload, content_payload = None, None
            if isinstance(req.data, (dict, list)):
                json_payload = req.data
            elif isinstance(req.data, str):
                content_payload = req.data.encode("utf-8")
            elif req.data is not None:
                json_payload = axon_service.from_any_to_object(req.data)
            
            response = await client.request(
                method=method,
                url=req.upstream_url,
                headers=req.headers,
                json=json_payload,
                content=content_payload,
            )
            response_status = response.status_code
            response_headers = dict(response.headers)
            response_body = response.content
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502, detail=f"Upstream connection failed: {exc}"
            ) from exc

    # Parse and encode response
    content_type = response_headers.get("content-type", "")
    decoded_text = response_body.decode("utf-8", errors="replace")
    
    if "application/json" in content_type:
        try:
            upstream_payload: Any = json.loads(decoded_text)
        except json.JSONDecodeError:
            upstream_payload = {"_raw_text": decoded_text}
    else:
        upstream_payload = {"_raw_text": decoded_text}

    # Convert to GCF envelope
    envelope = axon_service.convert_output(upstream_payload, session_id=req.session_id)
    envelope["upstream"] = {
        "url": req.upstream_url,
        "method": method,
        "status": response_status,
        "content_type": content_type,
    }
    
    # Log to persistent memory
    if req.session_id:
        event_payload = {
            "url": req.upstream_url,
            "method": method,
            "status": response_status,
            "tokens_saved": envelope["metrics"]["estimated_savings_percent"],
        }
        await memory_store.create_session(req.session_id)
        await memory_store.log_event(
            req.session_id,
            "upstream_proxy",
            event_payload,
        )

    return JSONResponse(status_code=response_status, content=envelope)
