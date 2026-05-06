"""Declarative SQLAlchemy base.

Single source of truth for the model class hierarchy. Alembic autogenerates
migrations against this `Base.metadata`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base class every model inherits from."""

    # Default __tablename__ derives from class name in snake_case.
    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        # CamelCase -> snake_case (User -> user, RefreshToken -> refresh_token)
        name = cls.__name__
        out: list[str] = []
        for i, ch in enumerate(name):
            if i and ch.isupper():
                out.append("_")
            out.append(ch.lower())
        return "".join(out)


class TimestampMixin:
    """Adds created_at / updated_at columns. Use as a mixin alongside Base."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """Adds a UUID primary key. Use for everything except join tables that
    don't need their own identity."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


# Re-export everything callers might import. Importing `Base` alone is the
# common case (for declaring new models).
__all__ = ["Base", "TimestampMixin", "UUIDMixin"]


# Help mypy understand the Any imports above (alembic-generated migrations
# sometimes import these and complain otherwise).
_ = Any
