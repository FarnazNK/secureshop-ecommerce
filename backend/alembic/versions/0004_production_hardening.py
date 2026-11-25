"""production hardening: idempotency, refunds/disputes, webhook log, shared rate limit

Revision ID: 0004_production_hardening
Revises: 0003_stripe_checkout
Create Date: 2026-11-24

Additive only (new nullable/defaulted columns, new tables, new indexes), so it
is safe to apply before deploying the code that uses it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_production_hardening"
down_revision: str | None = "0003_stripe_checkout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("order", sa.Column("idempotency_key", sa.String(255), nullable=True))
    op.add_column(
        "order",
        sa.Column("amount_refunded", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column("order", sa.Column("dispute_status", sa.String(40), nullable=True))
    op.create_unique_constraint(
        "uq_order_user_idempotency_key", "order", ["user_id", "idempotency_key"]
    )
    op.create_index("ix_order_user_created", "order", ["user_id", "created_at"])
    op.create_index("ix_order_status_created", "order", ["status", "created_at"])
    op.create_index("ix_order_stripe_payment_intent_id", "order", ["stripe_payment_intent_id"])
    # Storefront listing: WHERE is_active ORDER BY created_at DESC LIMIT n
    op.create_index("ix_product_active_created", "product", ["is_active", "created_at"])

    op.create_table(
        "stripe_event",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("outcome", sa.String(60), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("stripe_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_stripe_event_status_received", "stripe_event", ["status", "received_at"])

    op.create_table(
        "rate_limit_bucket",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("window_start", sa.BigInteger(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_bucket")
    op.drop_index("ix_stripe_event_status_received", table_name="stripe_event")
    op.drop_table("stripe_event")
    op.drop_index("ix_product_active_created", table_name="product")
    op.drop_index("ix_order_stripe_payment_intent_id", table_name="order")
    op.drop_index("ix_order_status_created", table_name="order")
    op.drop_index("ix_order_user_created", table_name="order")
    op.drop_constraint("uq_order_user_idempotency_key", "order", type_="unique")
    op.drop_column("order", "dispute_status")
    op.drop_column("order", "amount_refunded")
    op.drop_column("order", "idempotency_key")
