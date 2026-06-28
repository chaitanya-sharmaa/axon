"""Environment-driven settings for Axon Bridge."""

from __future__ import annotations

from dataclasses import dataclass
import os

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file before reading any os.getenv() calls
except ImportError:
    pass  # python-dotenv is optional during testing


_DEFAULT_ALLOWED_DOMAINS = [
    "httpbin.org",
    "api.github.com",
    "api.example.com",
    "localhost",
    "127.0.0.1",
]


def _as_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _as_list(raw: str | None, default: list[str]) -> list[str]:
    if raw is None:
        return list(default)
    values = [x.strip() for x in raw.split(",") if x.strip()]
    return values if values else list(default)


@dataclass
class AppSettings:
    app_title: str
    app_version: str
    app_description: str
    openapi_description: str
    openapi_logo_url: str

    host: str
    port: int

    include_json_fallback: bool
    memory_db_path: str
    memory_type: str  # "sqlite" | "redis"
    redis_url: str

    require_api_key: bool
    allow_all_domains: bool
    api_key: str | None
    allowed_domains: list[str]

    route_prefix_core: str
    route_prefix_process: str
    route_prefix_proxy: str
    route_prefix_memory: str
    route_prefix_security: str

    enable_core_routes: bool
    enable_process_routes: bool
    enable_proxy_routes: bool
    enable_memory_routes: bool
    enable_security_routes: bool
    enable_agent_routes: bool
    enable_openai_routes: bool
    
    # Feature Flags
    enable_semantic_routing: bool
    enable_exact_match_cache: bool
    enable_tool_compression: bool
    enable_rag_context: bool

    # Agentic Optimization Pipeline Feature Flags
    enable_agentic_optimizations: bool     # Master switch for the whole pipeline
    enable_agentic_schema_diff: bool       # Tool schema differential transmission
    enable_agentic_scratchpad: bool        # ReAct scratchpad compression
    enable_agentic_observation_window: bool # Entropy-based observation pruning
    enable_agentic_loop_detection: bool    # Tool loop circuit breaker

    # Admin & Quotas
    enable_tenant_quotas: bool
    admin_api_key: str | None

    # Logging
    log_format: str   # "text" | "json"
    log_level: str

    # Token optimizer — comma-separated list of strategies to benchmark
    tokenizer_model: str
    # choices: graph, graph_session, graph_delta, generic, generic_delta, generic_session, schema_values, json
    enabled_formats: list[str]
    max_sessions: int



def load_settings() -> AppSettings:
    port_raw = os.getenv("AXON_PORT", "8080")
    try:
        port = int(port_raw)
    except ValueError:
        port = 8080

    return AppSettings(
        app_title=os.getenv("AXON_APP_TITLE", "Axon Token Bridge"),
        app_version=os.getenv("AXON_APP_VERSION", "0.3.0"),
        app_description=os.getenv(
            "AXON_APP_DESCRIPTION",
            "Token-efficient bridge layer with session deduplication, security, and persistence",
        ),
        openapi_description=os.getenv(
            "AXON_OPENAPI_DESCRIPTION",
            "Token-efficient LLM proxy: ~29% API token savings via Schema Flattening, 99% network bandwidth savings via Stateful Threads (SQLite). Zero hallucination risk on stateless APIs.",
        ),
        openapi_logo_url=os.getenv("AXON_OPENAPI_LOGO_URL", ""),
        host=os.getenv("AXON_HOST", "127.0.0.1"),
        port=port,
        include_json_fallback=_as_bool(os.getenv("AXON_INCLUDE_JSON_FALLBACK"), True),
        memory_db_path=os.getenv("AXON_MEMORY_DB_PATH", "./axon_sessions.db"),
        memory_type=os.getenv("AXON_MEMORY_TYPE", "sqlite").lower(),
        redis_url=os.getenv("AXON_REDIS_URL", "redis://localhost:6379/0"),
        require_api_key=_as_bool(os.getenv("AXON_REQUIRE_API_KEY"), False),
        allow_all_domains=_as_bool(os.getenv("AXON_ALLOW_ALL_DOMAINS"), False),
        api_key=os.getenv("AXON_API_KEY"),
        allowed_domains=_as_list(os.getenv("AXON_ALLOWED_DOMAINS"), _DEFAULT_ALLOWED_DOMAINS),
        route_prefix_core=os.getenv("AXON_ROUTE_PREFIX_CORE", ""),
        route_prefix_process=os.getenv("AXON_ROUTE_PREFIX_PROCESS", ""),
        route_prefix_proxy=os.getenv("AXON_ROUTE_PREFIX_PROXY", "/proxy"),
        route_prefix_memory=os.getenv("AXON_ROUTE_PREFIX_MEMORY", "/memory"),
        route_prefix_security=os.getenv("AXON_ROUTE_PREFIX_SECURITY", "/security"),
        enable_core_routes=_as_bool(os.getenv("AXON_ENABLE_CORE_ROUTES"), True),
        enable_process_routes=_as_bool(os.getenv("AXON_ENABLE_PROCESS_ROUTES"), True),
        enable_proxy_routes=_as_bool(os.getenv("AXON_ENABLE_PROXY_ROUTES"), True),
        enable_memory_routes=_as_bool(os.getenv("AXON_ENABLE_MEMORY_ROUTES"), True),
        enable_security_routes=_as_bool(os.getenv("AXON_ENABLE_SECURITY_ROUTES"), True),
        enable_agent_routes=_as_bool(os.getenv("AXON_ENABLE_AGENT_ROUTES"), True),
        enable_openai_routes=_as_bool(os.getenv("AXON_ENABLE_OPENAI_ROUTES"), True),
        enable_semantic_routing=_as_bool(os.getenv("AXON_ENABLE_SEMANTIC_ROUTING"), True),
        enable_exact_match_cache=_as_bool(os.getenv("AXON_ENABLE_EXACT_MATCH_CACHE"), True),
        enable_tool_compression=_as_bool(os.getenv("AXON_ENABLE_TOOL_COMPRESSION"), True),
        enable_rag_context=_as_bool(os.getenv("AXON_ENABLE_RAG_CONTEXT"), True),
        enable_agentic_optimizations=_as_bool(os.getenv("AXON_ENABLE_AGENTIC_OPTIMIZATIONS"), True),
        enable_agentic_schema_diff=_as_bool(os.getenv("AXON_ENABLE_AGENTIC_SCHEMA_DIFF"), True),
        enable_agentic_scratchpad=_as_bool(os.getenv("AXON_ENABLE_AGENTIC_SCRATCHPAD"), True),
        enable_agentic_observation_window=_as_bool(os.getenv("AXON_ENABLE_AGENTIC_OBSERVATION_WINDOW"), True),
        enable_agentic_loop_detection=_as_bool(os.getenv("AXON_ENABLE_AGENTIC_LOOP_DETECTION"), True),
        enable_tenant_quotas=_as_bool(os.getenv("AXON_ENABLE_TENANT_QUOTAS"), False),
        admin_api_key=os.getenv("AXON_ADMIN_API_KEY"),
        log_format=os.getenv("AXON_LOG_FORMAT", "text"),
        log_level=os.getenv("AXON_LOG_LEVEL", "INFO"),
        tokenizer_model=os.getenv("AXON_TOKENIZER_MODEL", "cl100k_base"),
        enabled_formats=_as_list(
            os.getenv("AXON_ENABLED_FORMATS"),
            [
                "graph",
                "graph_session",
                "graph_delta",
                "generic",
                "generic_delta",
                "generic_session",
                "schema_values",
                "json",
            ]
        ),
        max_sessions=int(os.getenv("AXON_MAX_SESSIONS", "1000")),
    )


settings = load_settings()
