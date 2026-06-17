"""Environment-driven settings for GCF Bridge."""

from __future__ import annotations

from dataclasses import dataclass
import os


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


@dataclass(frozen=True)
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

    # Token optimizer — comma-separated list of strategies to benchmark
    tokenizer_model: str
    # choices: gcf_graph, gcf_session, gcf_delta, gcf_generic, json
    # choices: graph, graph_session, graph_delta, generic, generic_delta, generic_session, schema_values, json
    enabled_formats: list[str]



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
            "Token-efficient bridge with 25-71% savings (up to 70%+ in multi-turn sessions)",
        ),
        openapi_logo_url=os.getenv("AXON_OPENAPI_LOGO_URL", ""),
        host=os.getenv("AXON_HOST", "127.0.0.1"),
        port=port,
        include_json_fallback=_as_bool(os.getenv("AXON_INCLUDE_JSON_FALLBACK"), True),
        memory_db_path=os.getenv("AXON_MEMORY_DB_PATH", "/tmp/axon_sessions.db"),
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
        tokenizer_model=os.getenv("AXON_TOKENIZER_MODEL", "cl100k_base"), # Default for GPT-4, GPT-3.5-turbo
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
    )


settings = load_settings()
