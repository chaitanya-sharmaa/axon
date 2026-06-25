"""Route modules for Axon Bridge API."""

from .core_routes import router as core_router
from .process_routes import router as process_router
from .proxy_routes import router as proxy_router
from .memory_routes import router as memory_router
from .security_routes import router as security_router
from .agent_routes import router as agent_router
from .v1_openai_routes import router as openai_router
from .v1_assistants_routes import router as assistants_router
from .batch_routes import router as batch_router
from .admin_routes import router as admin_router


__all__ = [
    "core_router",
    "process_router",
    "proxy_router",
    "memory_router",
    "security_router",
    "agent_router",
    "openai_router",
    "assistants_router",
    "batch_router",
    "admin_router",
]
