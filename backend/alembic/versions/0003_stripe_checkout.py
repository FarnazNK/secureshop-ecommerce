"""stripe checkout session + paid timestamp on orders

Revision ID: 0003_stripe_checkout
Revises: 0002_demo_catalog
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_stripe_checkout"
down_revision: str | None = "0002_demo_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("order", sa.Column("stripe_checkout_session_id", sa.String(255), nullable=True))
    op.add_column("order", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_order_stripe_checkout_session_id", "order", ["stripe_checkout_session_id"])


def downgrade() -> None:
    op.drop_index("ix_order_stripe_checkout_session_id", table_name="order")
    op.drop_column("order", "paid_at")
    op.drop_column("order", "stripe_checkout_session_id")
