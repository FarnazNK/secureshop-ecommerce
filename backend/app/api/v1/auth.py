"""Auth endpoints — register, login, refresh, logout, me, password reset.

Routes are deliberately thin — all business logic lives in `services.auth_service`.
This file's job is to translate HTTP into service calls and back.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.services import auth_service
from app.services.auth_service import AuthError

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set the refresh token in an HTTP-only cookie. We use this everywhere
    the refresh token is issued so cookie semantics stay consistent."""
    settings = get_settings()
    max_age = settings.JWT_REFRESH_EXPIRY_DAYS * 24 * 60 * 60
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        max_age=max_age,
        path="/api/v1/auth",  # cookie only sent to auth routes
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        domain=settings.COOKIE_DOMAIN,
    )


def _to_token_response(user: User, access_token: str) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        user=UserPublic(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            email_verified=user.email_verified,
        ),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    try:
        user = await auth_service.register_user(
            db,
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    access, refresh = await auth_service.issue_token_pair(db, user)
    _set_refresh_cookie(response, refresh)
    return _to_token_response(user, access)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange credentials for tokens",
)
async def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    try:
        user = await auth_service.authenticate(db, email=payload.email, password=payload.password)
    except AuthError as exc:
        # Map specific codes to status codes; default to 401.
        code = status.HTTP_401_UNAUTHORIZED
        if exc.code == "account_locked":
            code = status.HTTP_423_LOCKED
        raise HTTPException(status_code=code, detail=str(exc)) from exc

    access, refresh = await auth_service.issue_token_pair(db, user)
    _set_refresh_cookie(response, refresh)
    return _to_token_response(user, access)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token, issue new access token",
)
async def refresh_tokens(
    payload: RefreshRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    cookie_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> TokenResponse:
    # Cookie wins over body — clients should be using cookies, body is fallback
    # for non-browser clients.
    refresh_token = cookie_token or payload.refresh_token
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing refresh token"
        )
    try:
        access, new_refresh, user = await auth_service.rotate_refresh_token(db, refresh_token)
    except AuthError as exc:
        # On compromise, also clear the cookie — client shouldn't reuse it.
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_refresh_cookie(response, new_refresh)
    return _to_token_response(user, access)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke the current refresh token",
)
async def logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    cookie_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> MessageResponse:
    if cookie_token:
        await auth_service.logout(db, cookie_token)
    _clear_refresh_cookie(response)
    return MessageResponse(message="logged out")


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Current authenticated user",
)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserPublic:
    return UserPublic(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        email_verified=user.email_verified,
    )
