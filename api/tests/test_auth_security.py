"""Security-sensitive authentication configuration behavior."""

from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url
from sqlmodel import select
from starlette.requests import Request

from api.api_keys import issue_api_key
from api.authorization import ensure_personal_workspace
from api.config import Settings
from api.models.entities import BrowserSession, Project
from api.routes.auth import _cookie_kwargs, _redirect_uri
from api.security import rate_limiter
from api.utils.time import utcnow


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


def test_production_rejects_local_auth():
    settings = _production_settings(local_auth_enabled=True)

    with pytest.raises(RuntimeError, match="LOCAL_AUTH_ENABLED"):
        settings.validate_production()


@pytest.mark.parametrize("days", [6, 91])
def test_recovery_window_rejects_unsafe_bounds(days: int):
    settings = _production_settings(deletion_recovery_days=days)

    with pytest.raises(RuntimeError, match="DELETION_RECOVERY_DAYS"):
        settings.validate_production()


@pytest.mark.parametrize("days", [7, 30, 90])
def test_recovery_window_accepts_supported_bounds(days: int):
    _production_settings(deletion_recovery_days=days).validate_production()


def test_neon_pooler_url_uses_documented_direct_realtime_host():
    settings = Settings(
        _env_file=None,
        database_url=(
            "postgresql://app:secret@"
            "ep-example-pooler.us-east-2.aws.neon.tech/mouvadah"
            "?sslmode=require"
        ),
    )

    realtime = make_url(settings.effective_realtime_database_url())

    assert realtime.host == "ep-example.us-east-2.aws.neon.tech"
    assert realtime.database == "mouvadah"
    assert realtime.password == "secret"


def test_realtime_override_must_target_application_database():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://app:secret@pooled.example/mouvadah",
        realtime_database_url=(
            "postgresql://app:secret@direct.example/other"
        ),
    )

    with pytest.raises(RuntimeError, match="application database"):
        settings.effective_realtime_database_url()


def test_realtime_override_must_use_application_database_user():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://app:secret@pooled.example/mouvadah",
        realtime_database_url=(
            "postgresql://other:secret@direct.example/mouvadah"
        ),
    )

    with pytest.raises(RuntimeError, match="application database user"):
        settings.effective_realtime_database_url()


@pytest.mark.parametrize(
    "frontend_url",
    [
        "http://192.168.1.20:5173",
        "http://devbox.internal:5173",
    ],
)
def test_local_auth_is_restricted_to_loopback(frontend_url: str):
    settings = Settings(
        _env_file=None,
        frontend_url=frontend_url,
        local_auth_enabled=True,
    )

    with pytest.raises(RuntimeError, match="loopback"):
        settings.validate_production()


def test_frontend_url_rejects_credentials():
    settings = Settings(
        _env_file=None,
        frontend_url="https://user:password@app.example.com",
    )

    with pytest.raises(RuntimeError, match="must not contain credentials"):
        settings.validate_production()


def _enable_local_auth(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_AUTH_ENABLED", "true")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    from api.config import get_settings

    get_settings.cache_clear()


def test_auth_providers_report_only_configured_methods(
    enforce_auth_client,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)

    response = enforce_auth_client.get("/api/v1/auth/providers")

    assert response.status_code == 200
    assert response.json() == {"google": False, "local_api_key": True}


def test_local_api_key_creates_httponly_session(
    enforce_auth_client,
    agent_headers,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)

    response = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": "test-agent-key"},
    )

    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    me = enforce_auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "test@example.com"


def test_local_api_key_rejects_bad_key(
    enforce_auth_client,
    agent_headers,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)

    response = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": "not-the-key"},
    )

    assert response.status_code == 401


def test_local_api_key_rejects_untrusted_origin_before_key_lookup(
    enforce_auth_client,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)

    response = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://evil.localhost:5173"},
        json={"api_key": "anything"},
    )

    assert response.status_code == 403


def test_local_api_key_endpoint_is_hidden_when_disabled(
    enforce_auth_client,
):
    response = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        json={"api_key": "anything"},
    )

    assert response.status_code == 404


def test_oauth_error_redirect_does_not_reflect_remote_input(client):
    response = client.get(
        "/api/v1/auth/callback?error=https://attacker.example/redirect",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == (
        "http://localhost:5173/?auth_error=oauth_denied"
    )
    assert "attacker" not in response.headers["location"]


def test_security_headers_are_applied_without_hsts_in_local_mode(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in response.headers[
        "content-security-policy"
    ]
    assert "strict-transport-security" not in response.headers


def test_hsts_is_applied_for_trusted_https_runtime(client, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://app.example.com")
    from api.config import get_settings

    get_settings.cache_clear()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )


def test_unsafe_cookie_request_rejects_cross_site_and_missing_origin(
    enforce_auth_client,
    agent_headers,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)
    login = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": "test-agent-key"},
    )
    assert login.status_code == 204

    cross_site = enforce_auth_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://evil.localhost:5173"},
    )
    missing = enforce_auth_client.post("/api/v1/auth/logout")

    assert cross_site.status_code == 403
    assert missing.status_code == 403
    assert enforce_auth_client.get("/api/v1/auth/me").status_code == 200


def test_invalid_explicit_bearer_never_falls_back_to_ambient_cookie(
    enforce_auth_client,
    agent_headers,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)
    login = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": "test-agent-key"},
    )
    assert login.status_code == 204

    response = enforce_auth_client.post(
        "/api/v1/projects",
        headers={"Authorization": "Bearer invalid"},
        json={"name": "Must not use cookie"},
    )

    assert response.status_code == 401


def test_malformed_explicit_authorization_never_uses_ambient_cookie(
    enforce_auth_client,
    agent_headers,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)
    login = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": "test-agent-key"},
    )
    assert login.status_code == 204

    response = enforce_auth_client.post(
        "/api/v1/projects",
        headers={"Authorization": "Basic explicit-but-unsupported"},
        json={"name": "Must not use cookie"},
    )

    assert response.status_code == 401


def test_logout_revokes_browser_session_immediately(
    enforce_auth_client,
    agent_headers,
    session,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)
    login = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": "test-agent-key"},
    )
    assert login.status_code == 204

    browser_session = session.exec(select(BrowserSession)).one()
    listed = enforce_auth_client.get("/api/v1/auth/sessions")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == browser_session.id
    assert listed.json()[0]["current"] is True
    logout = enforce_auth_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://localhost:5173"},
    )

    assert logout.status_code == 204
    session.refresh(browser_session)
    assert browser_session.revoked_at is not None
    assert enforce_auth_client.get("/api/v1/auth/me").status_code == 401


def test_server_side_session_revocation_invalidates_existing_cookie(
    enforce_auth_client,
    agent_headers,
    session,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)
    login = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": "test-agent-key"},
    )
    assert login.status_code == 204

    browser_session = session.exec(select(BrowserSession)).one()
    browser_session.revoked_at = utcnow()
    session.add(browser_session)
    session.commit()

    assert enforce_auth_client.get("/api/v1/auth/me").status_code == 401


def _scoped_key_fixture(session, test_user):
    workspace = ensure_personal_workspace(session, test_user)
    allowed = Project(workspace_id=workspace.id, name="Allowed")
    denied = Project(workspace_id=workspace.id, name="Denied")
    session.add_all([allowed, denied])
    session.commit()
    session.refresh(allowed)
    session.refresh(denied)
    api_key, raw_key = issue_api_key(
        session,
        user_id=test_user.id,
        workspace_id=workspace.id,
        name="read-only-project-key",
        scopes=["read"],
        project_ids=[allowed.id],
    )
    return api_key, raw_key, allowed, denied


def test_read_only_project_key_filters_lists_and_denies_writes(
    enforce_auth_client,
    session,
    test_user,
):
    api_key, raw_key, allowed, denied = _scoped_key_fixture(session, test_user)
    headers = {"Authorization": f"Bearer {raw_key}"}

    listed = enforce_auth_client.get("/api/v1/projects", headers=headers)
    denied_read = enforce_auth_client.get(
        f"/api/v1/projects/{denied.id}",
        headers=headers,
    )
    denied_write = enforce_auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "No write"},
    )

    assert listed.status_code == 200
    assert [project["id"] for project in listed.json()] == [allowed.id]
    assert denied_read.status_code == 404
    assert denied_write.status_code == 403
    assert "required scope: write" in denied_write.json()["detail"]

    api_key.revoked = True
    session.add(api_key)
    session.commit()
    assert (
        enforce_auth_client.get("/api/v1/projects", headers=headers).status_code
        == 401
    )


def test_bearer_scheme_is_case_insensitive_without_scope_escalation(
    enforce_auth_client,
    session,
    test_user,
):
    _, raw_key, allowed, _ = _scoped_key_fixture(session, test_user)

    denied_write = enforce_auth_client.post(
        f"/api/v1/projects/{allowed.id}/subprojects",
        headers={"Authorization": f"bearer {raw_key}"},
        json={"name": "No write", "context_brief": ""},
    )

    assert denied_write.status_code == 403
    assert "required scope: write" in denied_write.json()["detail"]


def test_project_restricted_write_key_cannot_create_unrestricted_project(
    enforce_auth_client,
    session,
    test_user,
):
    _, _, allowed, _ = _scoped_key_fixture(session, test_user)
    workspace = ensure_personal_workspace(session, test_user)
    _, raw_key = issue_api_key(
        session,
        user_id=test_user.id,
        workspace_id=workspace.id,
        name="restricted-writer",
        scopes=["read", "write"],
        project_ids=[allowed.id],
    )

    response = enforce_auth_client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={"name": "Outside allow-list"},
    )

    assert response.status_code == 403
    assert "Project-restricted" in response.json()["detail"]


def test_restricted_key_cannot_escalate_into_local_browser_session(
    enforce_auth_client,
    session,
    test_user,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)
    _, raw_key, _, _ = _scoped_key_fixture(session, test_user)

    response = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": raw_key},
    )

    assert response.status_code == 401


def test_api_keys_cannot_manage_other_api_keys(
    enforce_auth_client,
    agent_headers,
):
    response = enforce_auth_client.get(
        "/api/v1/apikeys",
        headers=agent_headers,
    )

    assert response.status_code == 403
    assert "browser session" in response.json()["detail"]


def test_auth_rate_limit_returns_retry_after(
    enforce_auth_client,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)
    monkeypatch.setenv("AUTH_RATE_LIMIT", "2")
    from api.config import get_settings

    get_settings.cache_clear()
    rate_limiter.reset()

    responses = [
        enforce_auth_client.post(
            "/api/v1/auth/local-session",
            headers={"Origin": "http://localhost:5173"},
            json={"api_key": "invalid"},
        )
        for _ in range(3)
    ]

    assert [response.status_code for response in responses] == [401, 401, 429]
    assert int(responses[-1].headers["retry-after"]) >= 1


def test_action_rate_limit_applies_to_authenticated_cookie_writes(
    enforce_auth_client,
    agent_headers,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)
    login = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": "test-agent-key"},
    )
    assert login.status_code == 204

    monkeypatch.setenv("ACTION_RATE_LIMIT", "2")
    from api.config import get_settings

    get_settings.cache_clear()
    rate_limiter.reset()
    responses = [
        enforce_auth_client.post(
            "/api/v1/projects",
            headers={"Origin": "http://localhost:5173"},
            json={"name": f"Limited {index}"},
        )
        for index in range(3)
    ]

    assert [response.status_code for response in responses] == [201, 201, 429]


def test_browser_creates_explicitly_scoped_project_key(
    enforce_auth_client,
    agent_headers,
    session,
    test_user,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)
    workspace = ensure_personal_workspace(session, test_user)
    project = Project(workspace_id=workspace.id, name="Scoped")
    session.add(project)
    session.commit()
    session.refresh(project)
    login = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": "test-agent-key"},
    )
    assert login.status_code == 204

    created = enforce_auth_client.post(
        "/api/v1/apikeys",
        headers={"Origin": "http://localhost:5173"},
        json={
            "name": "Read-only integration",
            "workspace_id": workspace.id,
            "scopes": ["read"],
            "project_ids": [project.id],
            "expires_in_days": 30,
        },
    )

    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["workspace_id"] == workspace.id
    assert payload["scopes"] == ["read"]
    assert payload["project_ids"] == [project.id]
    bearer = {"Authorization": f"Bearer {payload['key']}"}
    assert (
        enforce_auth_client.get(
            f"/api/v1/projects/{project.id}",
            headers=bearer,
        ).status_code
        == 200
    )
    assert (
        enforce_auth_client.post(
            f"/api/v1/projects/{project.id}/subprojects",
            headers=bearer,
            json={"name": "Denied", "context_brief": ""},
        ).status_code
        == 403
    )


def test_browser_cannot_bind_key_to_project_from_another_workspace(
    enforce_auth_client,
    agent_headers,
    session,
    test_user,
    monkeypatch,
):
    _enable_local_auth(monkeypatch)
    personal = ensure_personal_workspace(session, test_user)
    login = enforce_auth_client.post(
        "/api/v1/auth/local-session",
        headers={"Origin": "http://localhost:5173"},
        json={"api_key": "test-agent-key"},
    )
    assert login.status_code == 204
    origin = {"Origin": "http://localhost:5173"}
    other_workspace = enforce_auth_client.post(
        "/api/v1/workspaces",
        headers=origin,
        json={"name": "Other workspace"},
    ).json()
    other_project = enforce_auth_client.post(
        "/api/v1/projects",
        headers=origin,
        json={
            "name": "Other project",
            "workspace_id": other_workspace["id"],
        },
    ).json()

    response = enforce_auth_client.post(
        "/api/v1/apikeys",
        headers=origin,
        json={
            "name": "Cross-workspace attempt",
            "workspace_id": personal.id,
            "scopes": ["read"],
            "project_ids": [other_project["id"]],
        },
    )

    assert response.status_code == 422
    assert "key workspace" in response.json()["detail"]
