"""Authenticated, read-only product-assistance endpoint (disabled by default)."""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.agentcore_readonly import AgentCoreUnavailable, invoke_readonly_agent
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.product import Product
from app.models.user import User

router = APIRouter()


class ProductQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@router.post("/products/ask")
async def ask_about_products(
    payload: ProductQuestion,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    if os.environ.get("SECURESHOP_ENABLE_AGENTCORE", "").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")
    # Only public, active catalog data is available to this agent. No user,
    # cart, order, payment, credential, or administrative data is included.
    records = (
        await db.execute(
            select(Product)
            .where(Product.is_active.is_(True))
            .order_by(Product.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    context = "\n".join(
        f"Product: {p.name[:200]}; {str(p.short_description or '')[:300]}"
        for p in records
    )[:12000]
    if not context:
        return {"answer": "No products are available."}
    try:
        answer = await run_in_threadpool(
            invoke_readonly_agent,
            prompt=payload.question,
            context=context,
            authorized=True,
            tenant_id=str(user.id),
        )
    except AgentCoreUnavailable:
        raise HTTPException(status_code=503, detail="Assistant unavailable") from None
    return {"answer": answer}
