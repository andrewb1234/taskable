from __future__ import annotations

import pytest
from starlette.requests import Request

from api.config import Settings
from api.routes.auth import _cookie_kwargs, _redirect_uri


def _request(host: str = "internal:8000", forwarded_proto: str | None = None) -> Request:
    headers = [(b"host", host.encode())]
    if forwarded_proto:
        headers.append((b"x-forwarded-proto", forwarded_proto.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/auth/login",
            "raw_path": b"/api/v1/auth/login",
            "query_string": b"",
            "headers": headers,
            "server": ("internal", 8000),
            "client": ("127.0.0.1", 12345),
            "root_path": "",
        }
    )


def _production_settings(**overrides) -> Settings:
    values = {
        "frontend_url": "https://app.example.com",
        "jwt_secret": "j" * 32,
        "agent_api_key": "a" * 32,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_redirect_uri_ignores_spoofed_proxy_headers():
    request = _request(host="attacker.example", forwarded_proto="http")

    assert _redirect_uri(request, _production_settings()) == (
        "https://app.example.com/api/v1/auth/callback"
    )


def test_development_redirect_uri_preserves_request_port():
    settings = Settings(_env_file=None, frontend_url="http://localhost:5173")

    assert _redirect_uri(_request(host="localhost:8000"), settings) == (
        "http://localhost:8000/api/v1/auth/callback"
    )


def test_cookie_security_comes_from_trusted_frontend_config():
    assert _cookie_kwargs(_production_settings())["secure"] is True
    settings = Settings(_env_file=None, frontend_url="http://localhost:5173")
    assert _cookie_kwargs(settings)["secure"] is False


def test_production_rejects_default_agent_api_key():
    settings = _production_settings(agent_api_key="dev-agent-key-change-me")

    with pytest.raises(RuntimeError, match="AGENT_API_KEY"):
        settings.validate_production()


def test_development_allows_local_defaults():
    Settings(_env_file=None, frontend_url="http://localhost:5173").validate_production()
