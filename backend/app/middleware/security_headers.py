"""Security headers middleware. The Python equivalent of Express's Helmet —
adds the standard set of HTTP security headers on every response.

We don't use the `secure` package directly because its API drifts; this
hand-rolled version is small enough to maintain and lets us tune CSP per
environment without library opacity.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds OWASP-recommended security headers to every response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        settings = get_settings()

        # --- Always-on headers ---
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )
        # X-XSS-Protection is deprecated but some scanners still flag its absence.
        response.headers["X-XSS-Protection"] = "0"

        # --- HTTPS-only ---
        if settings.is_prod:
            # 1 year HSTS with includeSubDomains. Don't add `preload` until
            # you're committed — it's a one-way street.
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # --- CSP ---
        # Lenient CSP suitable for an SPA backed by a same-origin API. Tighten
        # per environment as the frontend stabilizes.
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://js.stripe.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.stripe.com; "
            "frame-src https://js.stripe.com https://hooks.stripe.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers["Content-Security-Policy"] = csp

        return response
