"""Security primitives.

Password hashing, JWT issuance/verification, and secure token generation.
Centralized here so the same crypto primitives flow through every layer.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# Bcrypt is the right default for password hashing — battle-tested, slow on
# purpose, with built-in salt. Cost factor comes from settings so we can
# tune it as hardware gets faster.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def hash_password(plaintext: str) -> str:
    """Hash a password with bcrypt. Cost factor is configurable in settings."""
    settings = get_settings()
    return _pwd_context.hash(plaintext, rounds=settings.BCRYPT_COST)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Constant-time password verification. Returns False on any error
    (including malformed hashes), never raises."""
    try:
        return _pwd_context.verify(plaintext, hashed)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

TokenType = Literal["access", "refresh"]


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    """Create a short-lived access token. `subject` is typically the user ID."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_EXPIRY_MINUTES),
        "jti": secrets.token_urlsafe(16),  # token ID for revocation lists
        **(claims or {}),
    }
    return jwt.encode(payload, settings.JWT_ACCESS_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    """Create a long-lived refresh token. Stored in HTTP-only cookie only."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_EXPIRY_DAYS),
        "jti": secrets.token_urlsafe(16),
        **(claims or {}),
    }
    return jwt.encode(payload, settings.JWT_REFRESH_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, token_type: TokenType) -> dict[str, Any]:
    """Decode and verify a token. Raises `JWTError` on any problem.

    We use distinct secrets per token type so an access token can't be
    repurposed as a refresh token even if a secret leaks.
    """
    settings = get_settings()
    secret = settings.JWT_ACCESS_SECRET if token_type == "access" else settings.JWT_REFRESH_SECRET
    payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != token_type:
        raise JWTError(f"token type mismatch: expected {token_type}, got {payload.get('type')}")
    return payload


# ---------------------------------------------------------------------------
# Secure random tokens (password reset, email verification)
# ---------------------------------------------------------------------------


def generate_secure_token(length: int = 32) -> str:
    """URL-safe random token suitable for password reset / email verification.

    Uses `secrets` (CSPRNG) — never `random` for any security-relevant value.
    """
    return secrets.token_urlsafe(length)
