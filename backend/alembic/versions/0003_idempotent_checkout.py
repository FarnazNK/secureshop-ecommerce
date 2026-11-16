"""Idempotent checkout and Stripe webhook processing.

- ``idempotency_key``: one row per (user, Idempotency-Key), written with the order it created.
- ``stripe_event``: webhook events already processed, keyed by Stripe's event id.
- ``order.stripe_payment_intent_id`` becomes unique, so each payment intent maps to one order.
  If an existing database holds duplicate intent ids, this fails; resolve them and re-run.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_idempotent_checkout"
down_revision: str | None = "0002_demo_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "idempotency_key",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("order.id", ondelete="CASCADE"),
            nullable=True,
        ),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "key", name="uq_idempotency_key_user_key"),
    )
    op.create_table(
        "stripe_event",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("type", sa.String(100), nullable=False),
        *_timestamps(),
    )
    op.create_unique_constraint(
        "uq_order_stripe_payment_intent_id", "order", ["stripe_payment_intent_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_order_stripe_payment_intent_id", "order", type_="unique")
    op.drop_table("stripe_event")
    op.drop_table("idempotency_key")
