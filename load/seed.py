"""Seed products for the k6 load test (local database only).

    cd backend && python ../load/seed.py

Creates or resets 20 everyday products with large stock and one
"limited drop" product with exactly LIMITED_STOCK units, which the
flash-sale scenario races for. Prints the product ids as JSON for k6.
"""

from __future__ import annotations

import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import async_session_maker  # noqa: E402
from app.models.product import Product  # noqa: E402

LIMITED_STOCK = 50


async def upsert(db, slug: str, name: str, price: str, stock: int) -> Product:
    product = await db.scalar(select(Product).where(Product.slug == slug))
    if product is None:
        product = Product(slug=slug, name=name, price=Decimal(price), images=[])
        db.add(product)
    product.stock_quantity = stock
    product.is_active = True
    product.description = "Synthetic load-test product"
    return product


async def main() -> None:
    host = get_settings().DATABASE_URL.hosts()[0]["host"]
    if host not in {"localhost", "127.0.0.1", "postgres"}:
        sys.exit(f"refusing to seed a non-local database ({host})")
    async with async_session_maker() as db:
        everyday = [
            await upsert(db, f"load-item-{i:02d}", f"Load item {i:02d}", "9.99", 1_000_000)
            for i in range(20)
        ]
        limited = await upsert(db, "load-limited-drop", "Limited drop", "49.00", LIMITED_STOCK)
        await db.commit()
        print(
            json.dumps(
                {
                    "everyday": [str(p.id) for p in everyday],
                    "limited": str(limited.id),
                    "limitedStock": LIMITED_STOCK,
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
