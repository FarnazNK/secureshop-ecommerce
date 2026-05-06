"""Common schema fragments used across resources."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints. Validated bounds stop callers
    from requesting absurd page sizes."""

    page: int = Field(default=1, ge=1, le=10_000)
    limit: int = Field(default=20, ge=1, le=100)


class PageMeta(BaseModel):
    """Pagination metadata returned with every paginated response."""

    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class Page(BaseModel, Generic[T]):
    """Generic paginated response. `items` is the list of T."""

    items: list[T]
    meta: PageMeta


class ErrorResponse(BaseModel):
    """Standardized error body. Returned by the global exception handler."""

    error: str
    detail: str | None = None
    code: str | None = None
