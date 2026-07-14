"""Environment-driven settings for Axon Bridge."""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any
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


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AXON_", 
        env_file=".env", 
        extra="ignore",
        env_parse_fallback=True
    )

    axon_env: str = Field(default="development")
    app_title: str = Field(default="Axon Token Bridge")
    app_version: str = Field(default="0.3.0")
    app_description: str = Field(
        default="Token-efficient bridge layer with session deduplication, security, and persistence"
    )
    openapi_description: str = Field(
        default="Token-efficient LLM proxy: ~29% API token savings via Schema Flattening, 99% network bandwidth savings via Stateful Threads (SQLite). Zero hallucination risk on stateless APIs."
    )
    openapi_logo_url: str = Field(default="")

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8080)

    include_json_fallback: bool = Field(default=True)
    # ── Memory ───────────────────────────────────────────────────────────────
    memory_type: str = Field(default="turso")  # "turso" | "sqlite" | "redis"
    memory_db_path: str = Field(default="./axon_sessions.db")  # @deprecated — use turso_url instead. Kept for backwards compatibility
    turso_url: str = Field(default="file:./axon_sessions.db")       # "file:./axon_sessions.db" or "libsql://..."
    turso_auth_token: str | None = Field(default=None)
    redis_url: str = Field(default="redis://localhost:6379/0")

    require_api_key: bool = Field(default=False)
    allow_all_domains: bool = Field(default=False)
    api_key: str | None = Field(default=None)
    allowed_domains: str | list[str] = Field(default_factory=lambda: list(_DEFAULT_ALLOWED_DOMAINS))

    route_prefix_core: str = Field(default="")
    route_prefix_process: str = Field(default="")
    route_prefix_proxy: str = Field(default="/proxy")
    route_prefix_memory: str = Field(default="/memory")
    route_prefix_security: str = Field(default="/security")

    enable_core_routes: bool = Field(default=True)
    enable_process_routes: bool = Field(default=True)
    enable_proxy_routes: bool = Field(default=False)
    enable_memory_routes: bool = Field(default=False)
    enable_security_routes: bool = Field(default=False)
    enable_agent_routes: bool = Field(default=False)
    enable_openai_routes: bool = Field(default=True)

    # ── Token-Compression Feature Flags (ON by default) ──────────────────────
    enable_exact_match_cache: bool = Field(default=True)       # L1 KV cache — 100% savings on repeated requests
    enable_semantic_cache: bool = Field(default=True)          # L2 semantic vector cache — catches paraphrased questions
    enable_tool_compression: bool = Field(default=True)        # Compress JSON Schema tool defs to Python signatures
    enable_vision_optimizer: bool = Field(default=True)        # Downscale 4K images to 768px (reduces vision tokens)

    # Agentic Optimization Pipeline Feature Flags (all ON by default)
    enable_agentic_optimizations: bool = Field(default=True)     # Master switch for the whole pipeline
    enable_agentic_schema_diff: bool = Field(default=True)       # Tool schema differential transmission
    enable_agentic_scratchpad: bool = Field(default=True)        # ReAct scratchpad compression
    enable_agentic_observation_window: bool = Field(default=True) # Entropy-based observation pruning
    enable_agentic_loop_detection: bool = Field(default=True)    # Tool loop circuit breaker

    # ── Non-Compression Feature Flags (OFF by default — opt-in via .env) ─────
    enable_semantic_routing: bool = Field(default=False)        # ML Smart Router: auto-switch lite/pro model tiers
    enable_rag_context: bool = Field(default=False)             # RAG context injection from uploaded files
    enable_prompt_firewall: bool = Field(default=False)         # Block 25+ jailbreak/prompt-injection patterns
    enable_pii_redaction: bool = Field(default=False)           # Auto-redact emails, SSNs, credit cards, phones
    enable_hallucination_guard: bool = Field(default=False)     # Shannon entropy guard on logprobs (blocks low-confidence)
    enable_fact_extraction: bool = Field(default=False)         # Extract & store semantic facts from conversations
    enable_assistants_routes: bool = Field(default=False)       # OpenAI Assistants API (beta.threads.*)
    enable_llmlingua_compression: bool = Field(default=False)   # Semantic NLP compression via LLMLingua-2

    # Admin & Quotas
    enable_tenant_quotas: bool = Field(default=False)
    admin_api_key: str | None = Field(default=None)

    # Logging
    log_format: str = Field(default="text")   # "text" | "json"
    log_level: str = Field(default="INFO")

    # Token optimizer — comma-separated list of strategies to benchmark
    tokenizer_model: str = Field(default="cl100k_base")
    # choices: graph, graph_session, graph_delta, generic, generic_delta, generic_session, schema_values, json
    enabled_formats: str | list[str] = Field(default_factory=lambda: [
        "graph",
        "graph_session",
        "graph_delta",
        "generic",
        "generic_delta",
        "generic_session",
        "schema_values",
        "json",
    ])
    max_sessions: int = Field(default=1000)

    @field_validator("allowed_domains", "enabled_formats", mode="before")
    @classmethod
    def split_comma_list(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v




def load_settings() -> AppSettings:
    """Load settings from environment variables."""
    # Map AXON namespace back to standard OpenAI variables for internal usage
    if "AXON_OPENAI_API_KEY" in os.environ:
        os.environ["OPENAI_API_KEY"] = os.environ["AXON_OPENAI_API_KEY"]
    if "AXON_OPENAI_BASE_URL" in os.environ:
        os.environ["OPENAI_BASE_URL"] = os.environ["AXON_OPENAI_BASE_URL"]

    settings_obj = AppSettings()

    if settings_obj.axon_env == "production" and not settings_obj.admin_api_key:
        raise ValueError("AXON_ADMIN_API_KEY must be set when AXON_ENV is 'production' to secure the admin endpoints.")

    return settings_obj


settings = load_settings()
