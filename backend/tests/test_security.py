"""Tests for password hashing and JWT issuance/verification.

These are pure unit tests — no DB, no HTTP. Fast feedback loop.
"""

from __future__ import annotations

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_secure_token,
    hash_password,
    verify_password,
)


class TestPasswords:
    def test_hash_then_verify_succeeds(self):
        h = hash_password("correct-horse-battery-staple")
        assert verify_password("correct-horse-battery-staple", h)

    def test_wrong_password_rejected(self):
        h = hash_password("correct-horse-battery-staple")
        assert not verify_password("wrong-password", h)

    def test_hash_includes_salt(self):
        # Same input should produce different hashes (because of random salt).
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2
        assert verify_password("same-password", h1)
        assert verify_password("same-password", h2)

    def test_malformed_hash_returns_false(self):
        # Should not raise — return False on malformed input.
        assert not verify_password("anything", "not-a-valid-bcrypt-hash")


class TestJWT:
    def test_access_token_roundtrip(self):
        token = create_access_token("user-123", claims={"role": "customer"})
        payload = decode_token(token, "access")
        assert payload["sub"] == "user-123"
        assert payload["role"] == "customer"
        assert payload["type"] == "access"
        assert "jti" in payload

    def test_refresh_token_roundtrip(self):
        token = create_refresh_token("user-123")
        payload = decode_token(token, "refresh")
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"

    def test_access_token_cant_be_decoded_as_refresh(self):
        access = create_access_token("user-1")
        with pytest.raises(JWTError):
            decode_token(access, "refresh")

    def test_refresh_token_cant_be_decoded_as_access(self):
        refresh = create_refresh_token("user-1")
        with pytest.raises(JWTError):
            decode_token(refresh, "access")

    def test_each_token_has_unique_jti(self):
        # Avoid token replay defenses being bypassed by colliding JTIs.
        tokens = [create_access_token("user-1") for _ in range(10)]
        jtis = [decode_token(t, "access")["jti"] for t in tokens]
        assert len(set(jtis)) == len(jtis)

    def test_tampered_token_rejected(self):
        token = create_access_token("user-1")
        # Flip one character in the signature.
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
        with pytest.raises(JWTError):
            decode_token(tampered, "access")


class TestSecureTokens:
    def test_generate_secure_token_length(self):
        # Length is in bytes pre-encoding; URL-safe base64 expands it.
        token = generate_secure_token(32)
        assert len(token) >= 40

    def test_secure_tokens_are_unique(self):
        tokens = [generate_secure_token() for _ in range(100)]
        assert len(set(tokens)) == len(tokens)
