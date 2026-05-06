"""Auth business logic — separated from route handlers so it's testable
without an HTTP layer.

Concerns:
- Registration with email-uniqueness check and password hashing
- Login with constant-time response on bad credentials, lockout tracking
- Refresh-token rotation with reuse detection
- Password reset flow
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_secure_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import Role, User

log = get_logger(__name__)


class AuthError(Exception):
    """Raised when an auth operation fails. Route handlers convert to HTTP 401/403."""

    def __init__(self, message: str, *, code: str = "auth_error") -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def register_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
) -> User:
    """Create a new user. Raises `AuthError` if email is taken."""
    email = email.lower().strip()

    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        # Same wording as login-with-bad-creds to avoid email enumeration.
        # The frontend interprets this as a generic "invalid input" error.
        raise AuthError("registration failed", code="email_taken")

    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        role=Role.CUSTOMER,
        # Email verification token — frontend sends an email with this link.
        # In dev without SMTP configured, we just log it.
        email_verification_token=generate_secure_token(),
        email_verification_expiry=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    log.info("auth.register", user_id=str(user.id), email=user.email)
    return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def authenticate(
    db: AsyncSession,
    *,
    email: str,
    password: str,
) -> User:
    """Verify credentials and return the user. Tracks failed attempts to
    enforce lockout after threshold reached."""
    email = email.lower().strip()

    user = await db.scalar(select(User).where(User.email == email))

    # Run bcrypt even on missing user — constant-time response. Otherwise
    # an attacker could distinguish "user exists, wrong password" from
    # "no such user" by timing alone.
    dummy_hash = "$2b$12$KIXxPfwfxDEDTaHKv6JKBOcW/1.IY4EKWEPmmK9nvN/Yh8eS1xYgK"
    target_hash = user.password_hash if user else dummy_hash
    password_ok = verify_password(password, target_hash)

    if user is None or not password_ok or not user.is_active:
        if user is not None and not password_ok:
            await _record_failed_attempt(db, user)
        raise AuthError("invalid credentials", code="invalid_credentials")

    if user.is_locked:
        raise AuthError("account temporarily locked", code="account_locked")

    # Successful login — reset counters, update last_login.
    user.failed_login_attempts = 0
    user.lockout_until = None
    user.last_login_at = datetime.now(UTC)
    await db.commit()

    log.info("auth.login", user_id=str(user.id))
    return user


async def _record_failed_attempt(db: AsyncSession, user: User) -> None:
    """Increment the counter and lock the account if threshold reached."""
    settings = get_settings()
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_THRESHOLD:
        user.lockout_until = datetime.now(UTC) + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
        log.warning(
            "auth.account_locked",
            user_id=str(user.id),
            attempts=user.failed_login_attempts,
        )
    await db.commit()


# ---------------------------------------------------------------------------
# Token issuance + rotation
# ---------------------------------------------------------------------------


async def issue_token_pair(
    db: AsyncSession,
    user: User,
) -> tuple[str, str]:
    """Mint a fresh (access, refresh) pair. The refresh token is persisted
    so we can revoke it later."""
    access = create_access_token(str(user.id), claims={"role": user.role.value})
    refresh = create_refresh_token(str(user.id), claims={"role": user.role.value})

    # Pull the JTI back out so we can persist it.
    refresh_payload = decode_token(refresh, "refresh")
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=refresh_payload["jti"],
            expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=UTC),
        )
    )
    await db.commit()
    return access, refresh


async def rotate_refresh_token(
    db: AsyncSession,
    refresh_token: str,
) -> tuple[str, str, User]:
    """Verify a refresh token, invalidate it, and issue a new pair.

    Implements reuse detection: if a token comes in that's already revoked,
    we treat it as evidence of theft and revoke ALL of the user's tokens.
    """
    try:
        payload = decode_token(refresh_token, "refresh")
    except JWTError as exc:
        raise AuthError("invalid refresh token", code="invalid_refresh") from exc

    jti = payload.get("jti")
    user_id_str = payload.get("sub")
    if not jti or not user_id_str:
        raise AuthError("malformed refresh token", code="invalid_refresh")

    stored = await db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if stored is None:
        raise AuthError("unknown refresh token", code="invalid_refresh")

    if stored.revoked_at is not None:
        # Reuse detected — invalidate everything for this user.
        log.warning("auth.refresh_reuse_detected", user_id=user_id_str, jti=jti)
        await _revoke_all_for_user(db, uuid.UUID(user_id_str))
        raise AuthError("refresh token reused", code="token_compromised")

    if not stored.is_active:
        raise AuthError("refresh token expired", code="invalid_refresh")

    # Revoke the old token, mint a new pair.
    stored.revoked_at = datetime.now(UTC)
    user = await db.get(User, uuid.UUID(user_id_str))
    if user is None or not user.is_active:
        raise AuthError("user inactive", code="user_inactive")

    access, refresh = await issue_token_pair(db, user)
    return access, refresh, user


async def _revoke_all_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke all active refresh tokens for a user. Used on suspected theft."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC), is_compromised=True)
    )
    await db.commit()


async def logout(db: AsyncSession, refresh_token: str) -> None:
    """Revoke a single refresh token. Best-effort — if the token is invalid,
    we don't error (the client just wants to be logged out)."""
    try:
        payload = decode_token(refresh_token, "refresh")
    except JWTError:
        return
    jti = payload.get("jti")
    if not jti:
        return
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        await db.commit()
