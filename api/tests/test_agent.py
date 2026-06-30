"""Agent surface: MR linking, flattened context, bearer auth."""

from __future__ import annotations

import os

from sqlmodel import select

from api.models.entities import AuditLog


def _seed(client):
    project = client.post("/api/v1/projects", json={"name": "P"}).json()
    sp = client.post(
        f"/api/v1/projects/{project['id']}/subprojects",
        json={
            "name": "Sprint 1",
            "context_brief": "Ship the MVP Kanban board with SSE.",
        },
    ).json()
    ticket = client.post(
        f"/api/v1/subprojects/{sp['id']}/tickets",
        json={
            "title": "Build API",
            "description": "FastAPI + SQLModel.",
            "assignee": "AGENT",
        },
    ).json()
    return sp["id"], ticket["id"]


def test_mr_link_uses_mocked_github_pat(client, monkeypatch, agent_headers):
    monkeypatch.setenv("GITHUB_PAT", "ghp_mocktoken123")
    _, ticket_id = _seed(client)

    response = client.post(
        f"/api/v1/tickets/{ticket_id}/mr",
        json={"url": "https://github.com/acme/taskable/pull/1"},
        headers=agent_headers,
    )
    assert response.status_code == 200
    assert response.json()["mr_link"] == "https://github.com/acme/taskable/pull/1"
    # Env mock is readable inside the test scope.
    assert os.environ["GITHUB_PAT"] == "ghp_mocktoken123"


def test_mr_link_writes_audit_log(client, session, agent_headers):
    _, ticket_id = _seed(client)
    client.post(
        f"/api/v1/tickets/{ticket_id}/mr",
        json={"url": "https://github.com/acme/taskable/pull/42"},
        headers=agent_headers,
    )
    logs = list(
        session.exec(select(AuditLog).where(AuditLog.ticket_id == ticket_id)).all()
    )
    assert any(log.action.value == "MR_LINKED" for log in logs)
    assert logs[-1].actor.value == "AGENT"


def test_agent_context_flattens_subproject_for_llm(client, agent_headers):
    sp_id, _ = _seed(client)
    response = client.get(
        f"/api/v1/agent/context/{sp_id}", headers=agent_headers
    )
    assert response.status_code == 200
    body = response.text
    assert "Sprint 1" in body
    assert "Ship the MVP Kanban board with SSE." in body
    assert "Build API" in body
    assert "[TODO/AGENT]" in body
    # Confirm we returned a string-ish plain payload, not JSON.
    assert response.headers["content-type"].startswith("text/plain")


def test_agent_endpoint_requires_bearer(enforce_auth_client, agent_headers):
    project = enforce_auth_client.post(
        "/api/v1/projects", json={"name": "P"}, headers=agent_headers
    ).json()
    sp = enforce_auth_client.post(
        f"/api/v1/projects/{project['id']}/subprojects",
        json={"name": "S"},
        headers=agent_headers,
    ).json()

    unauthed = enforce_auth_client.get(f"/api/v1/agent/context/{sp['id']}")
    assert unauthed.status_code == 401

    bad = enforce_auth_client.get(
        f"/api/v1/agent/context/{sp['id']}",
        headers={"Authorization": "Bearer wrong"},
    )
    assert bad.status_code == 401


def test_agent_context_404_for_unknown_subproject(client, agent_headers):
    r = client.get("/api/v1/agent/context/999", headers=agent_headers)
    assert r.status_code == 404
