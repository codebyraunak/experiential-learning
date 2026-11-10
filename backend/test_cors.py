import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.cors import LOCAL_ORIGINS, allowed_origins


def test_allowed_origins_preserves_local_and_parses_vercel_urls():
    origins = allowed_origins(
        " https://campusfix.vercel.app/, https://campusfix-git-feature.vercel.app "
    )

    assert all(origin in origins for origin in LOCAL_ORIGINS)
    assert "https://campusfix.vercel.app" in origins
    assert "https://campusfix-git-feature.vercel.app" in origins


def test_cors_preflight_allows_configured_origin_only():
    application = FastAPI()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins("https://campusfix.vercel.app"),
        allow_methods=["GET"],
        allow_headers=["Authorization"],
    )

    @application.get("/")
    def home():
        return {"ok": True}

    client = TestClient(application)
    allowed = client.options(
        "/",
        headers={
            "Origin": "https://campusfix.vercel.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    denied = client.options(
        "/",
        headers={
            "Origin": "https://unlisted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://campusfix.vercel.app"
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.parametrize(
    "invalid_origin",
    ["*", "https://example.com/path", "not-a-url", "https://user:pass@example.com"],
)
def test_invalid_cors_origins_are_rejected(invalid_origin):
    with pytest.raises(ValueError, match="Invalid origin"):
        allowed_origins(invalid_origin)
