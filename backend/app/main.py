"""FastAPI application factory.

Wires together: config, logging, middleware (security headers, request
logging, CORS, rate limiting), the v1 router, and the global exception
handler. Returns an ASGI app that uvicorn can serve.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from app.api.v1 import api_router
from app.api_reference import render_api_reference
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import RATE_LIMITED, build_rate_limiter
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

METRIC_REQUESTS = Counter(
    "secureshop_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
METRIC_DURATION = Histogram("secureshop_http_duration_seconds", "HTTP latency", ["method", "route"])

DB_POOL_EXHAUSTED = Counter(
    "secureshop_db_pool_exhausted_total", "Requests shed (503) because no DB connection was free"
)

log = get_logger(__name__)


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

    app = FastAPI(
        title="SecureShop API",
        description="Secure e-commerce API server (FastAPI port).",
        version="1.0.0",
        docs_url="/api/docs" if not settings.is_prod else None,
        redoc_url="/api/redoc" if not settings.is_prod else None,
        openapi_url="/api/openapi.json" if not settings.is_prod else None,
        lifespan=_lifespan,
    )

    # --- Rate limiting ---
    # RATE_LIMIT_BACKEND=memory counts per process; =database shares the count
    # across every instance through the existing Postgres (see core/rate_limit).
    app.state.rate_limiter = build_rate_limiter(settings.RATE_LIMIT_BACKEND)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # Stripe webhooks are authenticated by signature and retried by Stripe;
        # rate limiting them by IP would only drop real payment events.
        if request.url.path == "/api/v1/payments/webhook":
            return await call_next(request)
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
        decision = await request.app.state.rate_limiter.hit(
            key, limit, window_seconds, fail_open=not auth_path
        )
        if not decision.allowed:
            RATE_LIMITED.labels(bucket).inc()
            return _rate_limit_response(decision.retry_after)
        return await call_next(request)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        if request.url.path == "/metrics":
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
        started = time.monotonic()
        response = await call_next(request)
        route = getattr(request.scope.get("route"), "path", "unmatched")
        METRIC_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        METRIC_DURATION.labels(request.method, route).observe(time.monotonic() - started)
        return response

    # --- Compression ---
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # --- CORS ---
    # Important: list explicit origins, no `*` with credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
        expose_headers=["X-Request-ID", "Retry-After"],
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
            allowed_hosts=settings.allowed_hosts_list,
        )

    # --- Routes ---
    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": "SecureShop API",
            "status": "online",
            "health": "/api/v1/health",
            "products": "/api/v1/products",
        }

    app.include_router(api_router, prefix="/api")

    @app.get("/api/reference", response_class=HTMLResponse, include_in_schema=False)
    async def api_reference() -> HTMLResponse:
        return HTMLResponse(render_api_reference(app.openapi()))

    # --- Overload: no free database connection within DB_POOL_TIMEOUT_SECONDS ---
    # Shed load with a retryable 503 instead of a 500, so clients and load
    # balancers back off rather than treating it as a bug.
    @app.exception_handler(SQLAlchemyTimeoutError)
    async def _pool_exhausted_handler(
        request: Request, exc: SQLAlchemyTimeoutError
    ) -> JSONResponse:
        DB_POOL_EXHAUSTED.inc()
        log.warning("db.pool_exhausted", path=request.url.path)
        return JSONResponse(
            status_code=503,
            content={"error": "server busy, please retry"},
            headers={"Retry-After": "2"},
        )

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
