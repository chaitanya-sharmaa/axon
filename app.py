"""Token Bridge FastAPI application entry point.

The main app is now modular with routes organized by concern:
- Core: health, translate_in, translate_out
- Process: handler routing with session tracking
- Proxy: upstream HTTP forwarding with security
- Memory: session persistence and queries
- Security: domain allowlist and API key management
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from core.app_config import initialize_app, memory_store
from core.settings import settings
from api.routes import (
    core_router,
    process_router,
    proxy_router,
    memory_router,
    security_router,
    agent_router,
)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    # Initialize app components
    initialize_app()
    
    # Create FastAPI app
    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        description=settings.app_description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    @app.on_event("startup")
    async def startup_event():
        """Perform asynchronous startup tasks."""
        await memory_store.initialize()
    
    # Register route modules using configurable prefixes and toggles
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
    
    # Custom OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=settings.app_title,
            version=settings.app_version,
            description=settings.openapi_description,
            routes=app.routes,
        )
        if settings.openapi_logo_url:
            openapi_schema["info"]["x-logo"] = {"url": settings.openapi_logo_url}
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi
    
    return app


# Create global app instance for Uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
