"""Proxy endpoint: forward HTTP requests to upstream APIs with GCF response encoding."""

from __future__ import annotations

from typing import Any
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse

from domain.api_models import UpstreamProxyRequest
from core.app_config import bridge, memory_store, security_config


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
            detail=f"Domain not in allowlist. Allowed: {security_config.allowed_domains}",
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

    # Prepare request
    headers = dict(req.headers or {})
    body_bytes: bytes | None = None

    if req.data is not None:
        if isinstance(req.data, (dict, list, int, float, bool)) or req.data is None:
            body_bytes = json.dumps(req.data, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        elif isinstance(req.data, str):
            body_bytes = req.data.encode("utf-8")
            headers.setdefault("Content-Type", "text/plain; charset=utf-8")
        else:
            normalized = bridge.from_any_to_object(req.data)
            body_bytes = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

    http_request = Request(req.upstream_url, data=body_bytes, method=method)
    for key, value in headers.items():
        http_request.add_header(key, value)

    # Execute upstream request
    response_status = 200
    response_headers: dict[str, str] = {}
    response_body = b""

    try:
        with urlopen(http_request, timeout=req.timeout_seconds) as response:
            response_status = response.status
            response_headers = dict(response.headers.items())
            response_body = response.read()
    except HTTPError as http_err:
        response_status = http_err.code
        response_headers = dict(http_err.headers.items()) if http_err.headers else {}
        response_body = http_err.read() if http_err.fp is not None else b""
    except URLError as url_err:
        raise HTTPException(status_code=502, detail=f"Upstream connection failed: {url_err.reason}") from url_err

    # Parse and encode response
    content_type = response_headers.get("Content-Type", "")
    decoded_text = response_body.decode("utf-8", errors="replace")
    
    if "application/json" in content_type:
        try:
            upstream_payload: Any = json.loads(decoded_text)
        except json.JSONDecodeError:
            upstream_payload = {"_raw_text": decoded_text}
    else:
        upstream_payload = {"_raw_text": decoded_text}

    # Convert to GCF envelope
    envelope = bridge.convert_output(upstream_payload, session_id=req.session_id)
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
        memory_store.create_session(req.session_id)
        memory_store.log_event(
            req.session_id,
            "upstream_proxy",
            event_payload,
        )

    return JSONResponse(status_code=response_status, content=envelope)
