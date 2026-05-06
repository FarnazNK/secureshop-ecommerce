"""FastAPI application factory.

Wires together: config, logging, middleware (security headers, request
logging, CORS, rate limiting), the v1 router, and the global exception
handler. Returns an ASGI app that uvicorn can serve.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

log = get_logger(__name__)


# Limiter is module-level so route decorators can attach to it.
# slowapi reads the IP from request.client.host; for prod behind a proxy,
# wire X-Forwarded-For via TrustedHostMiddleware + ProxyHeadersMiddleware.
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    log.info("api.startup", env=settings.NODE_ENV, port=settings.PORT)
    yield
    log.info("api.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SecureShop API",
        description="Secure e-commerce API server (FastAPI port).",
        version="1.0.0",
        docs_url="/api/docs" if not settings.is_prod else None,
        redoc_url="/api/redoc" if not settings.is_prod else None,
        openapi_url="/api/openapi.json" if not settings.is_prod else None,
        lifespan=_lifespan,
    )

    # --- Rate limiter ---
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

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
        # Replace with your actual prod hostnames.
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["api.secureshop.example", "secureshop.example"],
        )

    # --- Routes ---
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
