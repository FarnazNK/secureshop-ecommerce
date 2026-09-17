"""FastAPI application factory.

Wires together: config, logging, middleware (security headers, request
logging, CORS, rate limiting), the v1 router, and the global exception
handler. Returns an ASGI app that uvicorn can serve.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

log = get_logger(__name__)

_rate_windows: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_limit_response(retry_after: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "rate limit exceeded"},
        headers={"Retry-After": str(max(1, retry_after))},
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    log.info("api.startup", env=settings.NODE_ENV, port=settings.PORT)
    yield
    log.info("api.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    docs_enabled = not settings.is_prod or settings.ENABLE_DOCS

    app = FastAPI(
        title="SecureShop API",
        description="Secure e-commerce API server (FastAPI port).",
        version="1.0.0",
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url="/api/redoc" if docs_enabled else None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
        lifespan=_lifespan,
    )

    # --- Rate limiting ---
    # Process-local is sufficient for the single-instance portfolio deployment.
    # Move this state to Redis before running multiple API instances.
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        now = time.monotonic()
        auth_path = request.url.path in {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
        }
        if auth_path:
            window_seconds = settings.AUTH_RATE_LIMIT_WINDOW_MINUTES * 60
            limit = settings.AUTH_RATE_LIMIT_MAX_REQUESTS
            bucket = "auth"
        else:
            window_seconds = settings.RATE_LIMIT_WINDOW_MINUTES * 60
            limit = settings.RATE_LIMIT_MAX_REQUESTS
            bucket = "api"

        key = f"{bucket}:{_client_ip(request)}"
        events = _rate_windows[key]
        while events and now - events[0] >= window_seconds:
            events.popleft()
        if len(events) >= limit:
            retry_after = int(window_seconds - (now - events[0])) if events else window_seconds
            return _rate_limit_response(retry_after)
        events.append(now)
        return await call_next(request)

    # --- Compression ---
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # --- CORS ---
    # Important: list explicit origins, no `*` with credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

    # --- Security headers ---
    app.add_middleware(SecurityHeadersMiddleware)

    # --- Request logging (must be outer-most non-CORS so it sees everything) ---
    app.add_middleware(RequestLoggingMiddleware)

    # --- Trusted hosts in prod ---
    if settings.is_prod:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts_list,
        )

    # --- Routes ---
    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        response = {
            "name": "SecureShop API",
            "status": "online",
            "health": "/api/v1/health",
            "products": "/api/v1/products",
        }
        if docs_enabled:
            response["docs"] = "/api/docs"
        return response

    app.include_router(api_router, prefix="/api")

    # --- Global exception handler ---
    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log the full traceback server-side; never leak it to the client.
        log.exception("unhandled_exception", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal server error"},
        )

    return app


# Module-level app for `uvicorn app.main:app` usage.
app = create_app()
