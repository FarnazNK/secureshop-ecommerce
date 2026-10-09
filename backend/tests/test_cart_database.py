"""Exercise cart aggregates with real async database sessions."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.cart import add_to_cart, clear_cart, get_cart
from app.db.base import Base
from app.models.product import Product
from app.models.user import User
from app.schemas.order import AddToCartRequest


@pytest.mark.asyncio
async def test_new_cart_and_mutations_load_complete_aggregate():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            user = User(
                email="cart-test@example.com",
                password_hash="unused-test-hash",
                first_name="Cart",
                last_name="Test",
            )
            product = Product(
                name="Test product",
                slug="test-product",
                description="Synthetic test product",
                price=Decimal("12.50"),
                stock_quantity=10,
                images=[],
            )
            db.add_all([user, product])
            await db.commit()
            empty = await get_cart(user=user, db=db)
            assert empty.items == []
            assert empty.subtotal == Decimal("0.00")
            added = await add_to_cart(
                AddToCartRequest(product_id=str(product.id), quantity=2), user=user, db=db
            )
            assert added.item_count == 2
            assert added.subtotal == Decimal("25.00")
            assert added.items[0].product.name == "Test product"
            cleared = await clear_cart(user=user, db=db)
            assert cleared.items == []
            assert cleared.item_count == 0
    finally:
        await engine.dispose()
