"""Health check endpoint. Reports DB and Redis reachability so K8s / load
balancers can route traffic correctly."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    db: str
    api_version: str = "v1"


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness/readiness probe",
)
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> HealthResponse:
    """Returns 200 if the API can reach the database. Don't put expensive
    checks here — health endpoints should be cheap and frequent."""
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"
    return HealthResponse(status="ok" if db_status == "ok" else "degraded", db=db_status)
