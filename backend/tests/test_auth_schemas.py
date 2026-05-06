"""Tests for auth request schema validation. Pure pydantic — no DB."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RegisterRequest


class TestRegisterRequest:
    def test_valid_registration(self):
        r = RegisterRequest(
            email="user@example.com",
            password="StrongPass123!",
            first_name="Ada",
            last_name="Lovelace",
        )
        assert r.email == "user@example.com"

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="not-an-email",
                password="StrongPass123!",
                first_name="A",
                last_name="B",
            )

    def test_short_password_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="Short1!",
                first_name="A",
                last_name="B",
            )

    def test_password_without_uppercase_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="alllowercase123",
                first_name="A",
                last_name="B",
            )

    def test_password_without_digit_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="NoDigitsHere",
                first_name="A",
                last_name="B",
            )

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="StrongPass123!",
                first_name="   ",  # only whitespace
                last_name="B",
            )


class TestLoginRequest:
    def test_login_accepts_any_password_format(self):
        # Login doesn't enforce strength — old passwords pre-policy still work.
        r = LoginRequest(email="user@example.com", password="anything")
        assert r.password == "anything"

    def test_login_requires_valid_email(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="not-email", password="x")
