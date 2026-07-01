"""Application configuration and initialization."""

from __future__ import annotations

from services.bridge_service import AxonService
from services.security_policy import SecurityConfig
from services.token_optimizer import TokenOptimizer
from services.agent_orchestrator import AgentOrchestrator, AgentDefinition
from domain.process_handlers import (
    handler_echo,
    handler_active_items,
    handler_graph_processor,
)
from core.settings import settings


# ── Security ──────────────────────────────────────────────────────────────────
security_config = SecurityConfig(
    api_key=settings.api_key,
    allowed_domains=settings.allowed_domains,
    require_api_key=settings.require_api_key,
    allow_all_domains=settings.allow_all_domains,
)

# ── Token optimizer — auto-picks cheapest encoding (Axon/TOON/TRON) ────────────
token_optimizer = TokenOptimizer(
    enabled_strategies=settings.enabled_formats,
    max_sessions=settings.max_sessions,
)

# ── Core bridge service (delegates session management to the optimizer) ─────────
axon_service = AxonService(
    token_optimizer=token_optimizer,
    include_json_fallback=settings.include_json_fallback,
)

from services.memory_store import BaseMemoryStore
from services.libsql_memory_store import LibsqlMemoryStore
from services.redis_memory_store import RedisMemoryStore

memory_store: BaseMemoryStore

if settings.memory_type == "redis":
    memory_store = RedisMemoryStore(redis_url=settings.redis_url)
else:
    # "turso" or "sqlite" will map to LibsqlMemoryStore
    # We mapped 'sqlite' to Turso/libSQL for backward compatibility
    url = settings.turso_url if settings.memory_type == "turso" else f"file:{settings.memory_db_path}"
    memory_store = LibsqlMemoryStore(url=url, auth_token=settings.turso_auth_token)

# ── Agent orchestrator — multi-agent dispatch layer ───────────────────────────
orchestrator = AgentOrchestrator(token_optimizer=token_optimizer)

# Register built-in agents
orchestrator.register(AgentDefinition(
    name="echo_agent",
    agent_type="generic",
    handler=handler_echo,
    capabilities=["echo", "passthrough"],
    priority=10,
    description="Echo handler — returns payload as-is",
))
orchestrator.register(AgentDefinition(
    name="active_items_agent",
    agent_type="analyzer",
    handler=handler_active_items,
    capabilities=["active_items", "filter", "list_analysis"],
    priority=5,
    description="Filters and counts active items from a list payload",
))
orchestrator.register(AgentDefinition(
    name="graph_agent",
    agent_type="analyzer",
    handler=handler_graph_processor,
    capabilities=["graph", "code_context", "symbol_analysis"],
    priority=0,
    description="Analyzes code-symbol graphs (symbols + edges)",
))


def initialize_app() -> dict[str, object]:
    return {
        "axon_service": axon_service,
        "memory_store": memory_store,
        "security_config": security_config,
        "token_optimizer": token_optimizer,
        "orchestrator": orchestrator,
    }


__all__ = [
    "axon_service", "memory_store", "security_config",
    "token_optimizer", "orchestrator", "initialize_app",
]
