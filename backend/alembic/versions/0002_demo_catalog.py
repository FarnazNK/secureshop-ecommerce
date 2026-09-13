"""seed synthetic demo catalog

Revision ID: 0002_demo_catalog
Revises: 0001_initial
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_demo_catalog"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORY_IDS = [
    "10000000-0000-4000-8000-000000000001",
    "10000000-0000-4000-8000-000000000002",
    "10000000-0000-4000-8000-000000000003",
    "10000000-0000-4000-8000-000000000004",
]

PRODUCT_IDS = [
    "20000000-0000-4000-8000-000000000001",
    "20000000-0000-4000-8000-000000000002",
    "20000000-0000-4000-8000-000000000003",
    "20000000-0000-4000-8000-000000000004",
]


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO category (id, name, slug, description)
            VALUES
              (:c1, 'Bags', 'bags', 'Synthetic portfolio demo category'),
              (:c2, 'Kitchen', 'kitchen', 'Synthetic portfolio demo category'),
              (:c3, 'Home', 'home', 'Synthetic portfolio demo category'),
              (:c4, 'Lighting', 'lighting', 'Synthetic portfolio demo category')
            ON CONFLICT DO NOTHING
            """
        ).bindparams(c1=CATEGORY_IDS[0], c2=CATEGORY_IDS[1], c3=CATEGORY_IDS[2], c4=CATEGORY_IDS[3])
    )

    op.execute(
        sa.text(
            """
            INSERT INTO product
              (id, name, slug, short_description, description, price, compare_at_price,
               stock_quantity, is_active, is_featured, category_id)
            VALUES
              (:p1, 'Minimal Leather Tote', 'minimal-leather-tote',
               'A clean-lined synthetic demo tote for the SecureShop portfolio.',
               'Portfolio demo product. No real merchandise is sold.', 189.00, 249.00, 14, true, true, :c1),
              (:p2, 'Ceramic Pour Over Set', 'ceramic-pour-over-set',
               'A synthetic demo coffee set for the SecureShop portfolio.',
               'Portfolio demo product. No real merchandise is sold.', 78.00, NULL, 22, true, true, :c2),
              (:p3, 'Merino Wool Throw', 'merino-wool-throw',
               'A synthetic demo home textile for the SecureShop portfolio.',
               'Portfolio demo product. No real merchandise is sold.', 145.00, NULL, 9, true, true, :c3),
              (:p4, 'Brass Desk Lamp', 'brass-desk-lamp',
               'A synthetic demo desk lamp for the SecureShop portfolio.',
               'Portfolio demo product. No real merchandise is sold.', 225.00, NULL, 7, true, true, :c4)
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            p1=PRODUCT_IDS[0], p2=PRODUCT_IDS[1], p3=PRODUCT_IDS[2], p4=PRODUCT_IDS[3],
            c1=CATEGORY_IDS[0], c2=CATEGORY_IDS[1], c3=CATEGORY_IDS[2], c4=CATEGORY_IDS[3],
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM product WHERE id = ANY(CAST(:ids AS uuid[]))").bindparams(ids=PRODUCT_IDS)
    )
    op.execute(
        sa.text("DELETE FROM category WHERE id = ANY(CAST(:ids AS uuid[]))").bindparams(ids=CATEGORY_IDS)
    )
