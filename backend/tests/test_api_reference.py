from app.api_reference import render_api_reference


def test_reference_escapes_metadata_and_marks_authentication():
    html = render_api_reference(
        {
            "info": {"title": "<script>unsafe</script>"},
            "paths": {
                "/api/v1/products": {
                    "get": {"summary": "<img src=x onerror=alert(1)>"},
                    "parameters": [],
                },
                "/api/v1/orders": {"post": {"security": [{"Bearer": []}]}},
            },
        }
    )
    assert "<script>" not in html
    assert "<img " not in html
    assert "&lt;script&gt;" in html
    assert "Authentication required" in html
    assert "Public" in html
    assert "PARAMETERS" not in html
    assert "<form" not in html


def test_production_reference_and_exact_hostname(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("NODE_ENV", "production")
    monkeypatch.setenv("ALLOWED_HOSTS", "portfolio.example.com")
    get_settings.cache_clear()
    try:
        with TestClient(create_app(), base_url="https://portfolio.example.com") as client:
            response = client.get("/api/reference")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/html")
            assert "/api/v1/products" in response.text
            assert "Content-Security-Policy" in response.headers
            assert client.get("/api/docs").status_code == 404
            assert client.get("/api/openapi.json").status_code == 404
            assert (
                client.get("/api/reference", headers={"host": "untrusted.example"}).status_code
                == 400
            )
    finally:
        get_settings.cache_clear()
