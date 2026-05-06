"""Test config loading. Verifies that required fields fail fast and that
the ALLOWED_ORIGINS validator splits comma-separated input correctly.
"""

from __future__ import annotations

from app.core.config import Settings


class TestSettings:
    def test_allowed_origins_splits_comma_string(self, monkeypatch):
        monkeypatch.setenv(
            "ALLOWED_ORIGINS",
            "http://a.com, http://b.com ,http://c.com",
        )
        from app.core.config import get_settings as _gs

        _gs.cache_clear()
        s = _gs()
        assert s.allowed_origins_list == ["http://a.com", "http://b.com", "http://c.com"]
        _gs.cache_clear()

    def test_allowed_origins_default(self, monkeypatch):
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        from app.core.config import get_settings as _gs

        _gs.cache_clear()
        s = _gs()
        assert "http://localhost:3000" in s.allowed_origins_list
        _gs.cache_clear()

    def test_is_prod_true_only_in_production(self, monkeypatch):
        monkeypatch.setenv("NODE_ENV", "production")
        s = Settings()  # type: ignore[call-arg]
        assert s.is_prod is True

        monkeypatch.setenv("NODE_ENV", "development")
        s = Settings()  # type: ignore[call-arg]
        assert s.is_prod is False
