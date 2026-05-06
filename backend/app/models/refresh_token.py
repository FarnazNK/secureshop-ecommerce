"""Refresh tokens are persisted so we can:
- Revoke individual tokens (logout from one device)
- Detect reuse (a revoked token being presented suggests theft → invalidate all)
- Enforce per-user session caps if needed later

We store the JTI (token ID), not the full token. The token itself stays
opaque on the client side in an HTTP-only cookie.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(Base, UUIDMixin, TimestampMixin):
    """A persisted refresh token reference. Lookup key is `jti`."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Set when explicitly revoked (logout, rotation, password change).
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # If true, presenting this token after revocation triggers a full session
    # invalidation for the user (we treat it as theft).
    is_compromised: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")

    @property
    def is_active(self) -> bool:
        from datetime import datetime

        return self.revoked_at is None and self.expires_at > datetime.now(UTC)
