import logging
import json
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from services.pricing import estimate_cost_usd

log = logging.getLogger(__name__)

class CostBudgetGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        max_cost_str = request.headers.get("X-Axon-Max-Cost")
        
        if max_cost_str is not None:
            try:
                max_cost = float(max_cost_str)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid X-Axon-Max-Cost header. Must be a float."}
                )

            if request.method == "POST" and "application/json" in request.headers.get("content-type", ""):
                body_bytes = await request.body()
                
                async def receive():
                    return {"type": "http.request", "body": body_bytes}
                request._receive = receive

                if body_bytes:
                    try:
                        body = json.loads(body_bytes)
                        model = body.get("model")
                        
                        if model:
                            json_text = json.dumps(body)
                            
                            from services.token_optimizer import _estimate_tokens
                            estimated_tokens = _estimate_tokens(json_text, model=model)
                            
                            cost = estimate_cost_usd(estimated_tokens, model, direction="input")
                            if cost is not None and cost > max_cost:
                                log.warning(f"CostBudgetGuard blocked request. Est Cost: ${cost}, Max: ${max_cost}")
                                try:
                                    from services.event_logger import event_logger
                                    event_logger.log_firewall_block(f"Cost Budget Exceeded (${cost} > ${max_cost})", tenant_id="default")
                                except Exception:
                                    pass

                                return JSONResponse(
                                    status_code=402,
                                    content={"error": f"Estimated input cost (${cost}) exceeds budget (${max_cost})"}
                                )
                    except json.JSONDecodeError:
                        pass
                    except Exception as e:
                        log.warning(f"CostBudgetGuard failed to estimate cost: {e}")

        response = await call_next(request)
        return response
