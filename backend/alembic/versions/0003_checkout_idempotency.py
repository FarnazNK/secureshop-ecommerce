"""add order idempotency key for safe checkout retries

Revision ID: 0003_checkout_idempotency
Revises: 0002_demo_catalog
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_checkout_idempotency"
down_revision: str | None = "0002_demo_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("order", sa.Column("idempotency_key", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_order_user_idempotency_key", "order", ["user_id", "idempotency_key"]
    )
    op.create_index(
        "ix_order_stripe_payment_intent_id", "order", ["stripe_payment_intent_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_order_stripe_payment_intent_id", table_name="order")
    op.drop_constraint("uq_order_user_idempotency_key", "order", type_="unique")
    op.drop_column("order", "idempotency_key")
