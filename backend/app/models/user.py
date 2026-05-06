"""User model. Includes auth state (password hash, lockout counters,
verification tokens) and PII (name, phone, addresses).

Sensitive fields are explicitly typed and indexed where they need to be
queried (email lookup at login). PII columns are left unencrypted at the
DB level — defense in depth here is row-level access policy + DB encryption
at rest, not column-level encryption (which would break indexing on email).
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.cart import Cart
    from app.models.order import Order
    from app.models.refresh_token import RefreshToken


class Role(enum.StrEnum):
    """User roles for RBAC. Order matters: higher index = more privileged."""

    CUSTOMER = "customer"
    STAFF = "staff"
    ADMIN = "admin"


class User(Base, UUIDMixin, TimestampMixin):
    """Application user."""

    # --- Identity ---
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Authorization ---
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=20),
        default=Role.CUSTOMER,
        nullable=False,
    )

    # --- Account state ---
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Email verification ---
    email_verification_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verification_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Password reset ---
    password_reset_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_reset_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Brute-force protection ---
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lockout_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    cart: Mapped[Cart | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    orders: Mapped[list[Order]] = relationship(back_populates="user")

    @property
    def is_locked(self) -> bool:
        """True if the account is currently locked due to failed logins."""
        from datetime import datetime

        return self.lockout_until is not None and self.lockout_until > datetime.now(UTC)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
