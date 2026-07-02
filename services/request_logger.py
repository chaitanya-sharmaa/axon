import time
import uuid
from collections import deque
from typing import Any


class RequestLogger:
    def __init__(self, maxlen: int = 500):
        self._logs = deque(maxlen=maxlen)

    def log_request(self,
                    model: str,
                    latency_ms: float,
                    prompt_tokens: int,
                    completion_tokens: int,
                    total_tokens: int,
                    cache_hit: bool = False,
                    tenant_id: str = "default",
                    cost: float = 0.0,
                    status_code: int = 200,
                    error: str = None):

        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "model": model,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "cache_hit": cache_hit,
            "tenant_id": tenant_id,
            "status_code": status_code,
            "error": error
        }
        self._logs.appendleft(entry)

    def get_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        # Returns the most recent logs
        logs = list(self._logs)
        return logs[:limit]

    def clear(self):
        self._logs.clear()

# Global Singleton
request_logger = RequestLogger()
