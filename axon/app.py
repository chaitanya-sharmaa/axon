"""Axon Bridge — FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env before any other import reads os.getenv()
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse

# OpenTelemetry imports
from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from axon.api.middleware.request_id import RequestIDMiddleware
from axon.api.routes import (
    admin_router,
    agent_router,
    assistants_router,
    batch_router,
    core_router,
    files_router,
    memory_router,
    openai_router,
    process_router,
    proxy_router,
    security_router,
)
from axon.api.routes.dashboard_routes import router as dashboard_router
from axon.api.routes.v1_swarm_routes import router as swarm_router
from axon.core.app_config import initialize_app, memory_store
from axon.core.logging_config import configure_logging
from axon.core.settings import settings

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the Axon FastAPI application."""

    # ── Logging ──────────────────────────────────────────────────────────────
    configure_logging(
        log_format=os.getenv("AXON_LOG_FORMAT", "text"),
        log_level=os.getenv("AXON_LOG_LEVEL", "INFO"),
    )

    # ── App components ────────────────────────────────────────────────────────
    initialize_app()

    # ── OpenTelemetry Setup ──────────────────────────────────────────────────
    # Tracing
    tracer_provider = TracerProvider()

    otlp_endpoint = os.getenv("AXON_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            log.info(f"OTLP Trace Exporter configured for {otlp_endpoint}")
        except ImportError:
            log.warning("opentelemetry-exporter-otlp not installed. Run `pip install opentelemetry-exporter-otlp` to enable OTLP traces.")

    trace.set_tracer_provider(tracer_provider)

    # Metrics via Prometheus
    metric_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("Axon Bridge %s starting up", settings.app_version)
        if hasattr(memory_store, "initialize"):
            await memory_store.initialize()
        yield
        log.info("Axon Bridge shutting down — closing connections")
        if hasattr(memory_store, "close"):
            await memory_store.close()

    # ── FastAPI ───────────────────────────────────────────────────────────────
    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        description=settings.app_description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Instrument the FastAPI app
    FastAPIInstrumentor.instrument_app(app)

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(RequestIDMiddleware)
    
    from axon.api.middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)
    
    from axon.api.middleware.cost_guard import CostBudgetGuardMiddleware
    app.add_middleware(CostBudgetGuardMiddleware)

    cors_origins = os.getenv("AXON_CORS_ORIGINS", "")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins.split(",") if cors_origins else [],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    if settings.enable_core_routes:
        app.include_router(core_router, prefix=settings.route_prefix_core)
    if settings.enable_process_routes:
        app.include_router(process_router, prefix=settings.route_prefix_process)
    if settings.enable_proxy_routes:
        app.include_router(proxy_router, prefix=settings.route_prefix_proxy)
    if settings.enable_memory_routes:
        app.include_router(memory_router, prefix=settings.route_prefix_memory)
    if settings.enable_security_routes:
        app.include_router(security_router, prefix=settings.route_prefix_security)
    if settings.enable_agent_routes:
        app.include_router(agent_router)

    # OpenAI-compatible routes (always at /v1)
    if settings.enable_openai_routes:
        app.include_router(openai_router)
        # Assistants API / Swarm / Files are opt-in (AXON_ENABLE_ASSISTANTS_ROUTES=true)
        if settings.enable_assistants_routes:
            app.include_router(assistants_router)
            app.include_router(swarm_router)
            app.include_router(files_router)

    # Batch processing
    app.include_router(batch_router)

    # Admin Quotas
    app.include_router(admin_router)

    # Dashboard
    app.include_router(dashboard_router)

    from fastapi.staticfiles import StaticFiles
    DASHBOARD_BUILD_DIR = os.path.join(os.path.dirname(__file__), "dashboard", "dist")
    if os.path.exists(DASHBOARD_BUILD_DIR):
        app.mount("/assets", StaticFiles(directory=os.path.join(DASHBOARD_BUILD_DIR, "assets")), name="dashboard_assets")

    # Health Check
    @app.get("/health", tags=["Ops"])
    def health_check():
        """Health check endpoint for load balancers."""
        return {"status": "ok", "version": settings.app_version}

    # Metrics
    @app.get("/metrics", tags=["Ops"])
    def get_metrics():
        """Expose Prometheus metrics."""
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # ── Custom OpenAPI schema ─────────────────────────────────────────────────
    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=settings.app_title,
            version=settings.app_version,
            description=settings.openapi_description,
            routes=app.routes,
        )
        if settings.openapi_logo_url:
            schema["info"]["x-logo"] = {"url": settings.openapi_logo_url}
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    return app


app = create_app()

if __name__ == "__main__":
    from granian import Granian
    Granian("app:app", address=settings.host, port=settings.port, interface="asgi").serve()
