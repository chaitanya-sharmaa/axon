"""Route modules for GCF Bridge API."""

from .core_routes import router as core_router
from .process_routes import router as process_router
from .proxy_routes import router as proxy_router
from .memory_routes import router as memory_router
from .security_routes import router as security_router
from .agent_routes import router as agent_router


__all__ = [
    "core_router",
    "process_router",
    "proxy_router",
    "memory_router",
    "security_router",
    "agent_router",
]
