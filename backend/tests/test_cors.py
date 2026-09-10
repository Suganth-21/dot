"""CORS must be an explicit allowlist — never allow_origins=["*"]
(CLAUDE.md rule 6, ARCHITECTURE.md §1.1 / §9.1)."""
from starlette.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.main import create_app


def test_cors_origins_setting_has_no_wildcard():
    settings = get_settings()
    assert "*" not in settings.cors_origins
    assert settings.cors_origins, "CORS_ORIGINS must configure at least one explicit origin"


def test_cors_middleware_registered_with_explicit_allowlist():
    app = create_app()
    cors_entries = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert cors_entries, "CORSMiddleware must be registered"
    kwargs = cors_entries[0].kwargs
    assert kwargs.get("allow_origins") != ["*"]
    assert "*" not in kwargs.get("allow_origins", [])


async def test_allowed_origin_gets_cors_header(client):
    resp = await client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


async def test_disallowed_origin_gets_no_cors_header(client):
    resp = await client.get("/api/health", headers={"Origin": "http://evil.example.com"})
    assert "access-control-allow-origin" not in resp.headers
