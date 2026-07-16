"""Simple in-memory rate limiting middleware using cachetools."""

import time
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from cachetools import TTLCache

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 200, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Store counts with a TTL of the window size + 1 to ensure it clears out
        self.cache = TTLCache(maxsize=10000, ttl=window_seconds + 1)

    async def dispatch(self, request: Request, call_next):
        # Allow internal health checks to bypass rate limits
        if request.url.path in ("/health", "/metrics"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        
        # Simple fixed window counter
        current_window = int(time.time() // self.window_seconds)
        cache_key = f"{client_ip}:{current_window}"
        
        count = self.cache.get(cache_key, 0)
        
        if count >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
                headers={"Retry-After": str(self.window_seconds)}
            )
            
        self.cache[cache_key] = count + 1
        return await call_next(request)
