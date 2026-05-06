"""Structured logging via structlog.

Produces JSON in production (machine-readable for log aggregators) and
human-friendly colored output in development. Idempotent — safe to call
`configure_logging` multiple times.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure stdlib logging + structlog. Call once at app startup."""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_prod:
        # JSON in prod for log aggregators (Loki, Datadog, etc.).
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Pretty console in dev.
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Project-wide logger factory. Always use this, never `logging.getLogger`."""
    return structlog.get_logger(name)
