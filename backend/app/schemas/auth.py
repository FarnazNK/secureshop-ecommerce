"""Auth-related request/response schemas.

Validation rules live here, not in the route handlers — this gives us a
single place to evolve password policy, email format, etc.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

from app.core.config import get_settings
from app.models.user import Role


# Password strength validator — runs before bcrypt. We enforce minimum length
# (configurable) and at least one of each character class. Deliberately not
# overly elaborate; really long passphrases beat short complex ones.
def _validate_password_strength(v: str) -> str:
    settings = get_settings()
    if len(v) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(f"password must be at least {settings.PASSWORD_MIN_LENGTH} characters")
    if not re.search(r"[A-Z]", v):
        raise ValueError("password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("password must contain at least one digit")
    return v


# Reusable type aliases.
NonEmptyStr = Annotated[str, StringConstraints(min_length=1, max_length=255, strip_whitespace=True)]


# --- Requests ---


class RegisterRequest(BaseModel):
    """POST /auth/register body."""

    email: EmailStr
    password: str
    first_name: NonEmptyStr
    last_name: NonEmptyStr

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginRequest(BaseModel):
    """POST /auth/login body."""

    email: EmailStr
    password: str  # we don't validate strength here — old passwords may not match policy


class RefreshRequest(BaseModel):
    """POST /auth/refresh body. Optional — the refresh token also comes via cookie."""

    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    password: str

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _validate_password_strength(v)


# --- Responses ---


class UserPublic(BaseModel):
    """User as exposed to the client. Never includes password_hash or tokens."""

    id: str
    email: EmailStr
    first_name: str
    last_name: str
    role: Role
    email_verified: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Returned on successful login / refresh."""

    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class MessageResponse(BaseModel):
    """Generic ack response for endpoints that don't need to return data."""

    message: str
