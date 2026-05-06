"""Runtime configuration.

All config flows through `Settings`. Read once at startup, treated as
immutable thereafter. Required values fail fast — better to crash at boot
than to start serving traffic with a missing JWT secret.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from env vars or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- App ---
    APP_NAME: str = "SecureShop"
    NODE_ENV: Literal["development", "test", "production"] = "development"
    PORT: int = 3001
    API_VERSION: str = "v1"

    # --- Database ---
    DATABASE_URL: PostgresDsn
    DATABASE_SSL: bool = False

    # --- Redis ---
    REDIS_URL: RedisDsn

    # --- JWT ---
    # Required, no defaults. We refuse to boot without them in any non-test env.
    JWT_ACCESS_SECRET: str = Field(min_length=32)
    JWT_REFRESH_SECRET: str = Field(min_length=32)
    JWT_ACCESS_EXPIRY_MINUTES: int = 15
    JWT_REFRESH_EXPIRY_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # --- Encryption (for any field-level encryption needs) ---
    ENCRYPTION_KEY: str = Field(min_length=32)

    # --- CORS ---
    # Stored as comma-separated string in env, exposed as a list via property.
    # pydantic-settings tries to JSON-parse list-typed env vars, which we don't want.
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    # --- Rate limiting ---
    RATE_LIMIT_WINDOW_MINUTES: int = 15
    RATE_LIMIT_MAX_REQUESTS: int = 100
    AUTH_RATE_LIMIT_WINDOW_MINUTES: int = 15
    AUTH_RATE_LIMIT_MAX_REQUESTS: int = 5  # tighter on auth endpoints

    # --- Cookies ---
    COOKIE_SECURE: bool = True  # Set False only for local HTTP dev
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "strict"
    COOKIE_DOMAIN: str | None = None

    # --- Stripe (optional in dev) ---
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_PUBLISHABLE_KEY: str | None = None

    # --- Email / SMTP (optional) ---
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASS: str | None = None
    EMAIL_FROM: str = "noreply@secureshop.example"

    # --- Frontend URL (for password reset emails etc.) ---
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Logging ---
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- Auth policy ---
    BCRYPT_COST: int = 12
    ACCOUNT_LOCKOUT_THRESHOLD: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 30
    PASSWORD_MIN_LENGTH: int = 12

    @property
    def is_prod(self) -> bool:
        return self.NODE_ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Tests can clear with `get_settings.cache_clear()`."""
    return Settings()  # type: ignore[call-arg]
