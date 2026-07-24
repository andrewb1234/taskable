"""Security-sensitive authentication configuration behavior."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from api.config import Settings
from api.routes.auth import _cookie_kwargs, _redirect_uri


def _request(
    host: str = "internal:8000",
    forwarded_proto: str | None = None,
) -> Request:
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
        "google_client_id": "client-id",
        "google_client_secret": "client-secret",
        "migration_mode": "check",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_redirect_uri_ignores_spoofed_request_origin():
    request = _request(host="attacker.example", forwarded_proto="http")

    assert _redirect_uri(request, _production_settings()) == (
        "https://app.example.com/api/v1/auth/callback"
    )


def test_production_redirect_uri_discards_configured_path_and_query():
    settings = _production_settings(
        frontend_url="https://app.example.com/some/path?source=unsafe"
    )

    assert _redirect_uri(_request(), settings) == (
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


@pytest.mark.parametrize(
    "secret",
    ["dev-jwt-secret-change-me", "too-short"],
)
def test_production_rejects_weak_jwt_secrets(secret: str):
    settings = _production_settings(jwt_secret=secret)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        settings.validate_production()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("google_client_id", None),
        ("google_client_secret", None),
    ],
)
def test_production_requires_google_credentials(field: str, value: None):
    settings = _production_settings(**{field: value})

    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT"):
        settings.validate_production()


def test_development_allows_local_auth_configuration_gaps():
    Settings(
        _env_file=None,
        frontend_url="http://localhost:5173",
    ).validate_production()


def test_production_requires_check_only_application_startup():
    settings = _production_settings(migration_mode="upgrade")

    with pytest.raises(RuntimeError, match="MIGRATION_MODE"):
        settings.validate_production()


def test_frontend_url_rejects_credentials():
    settings = Settings(
        _env_file=None,
        frontend_url="https://user:password@app.example.com",
    )

    with pytest.raises(RuntimeError, match="must not contain credentials"):
        settings.validate_production()
