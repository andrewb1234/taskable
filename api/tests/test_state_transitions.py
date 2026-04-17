"""PATCH /tickets/{id}: valid transitions, validation, and audit logging."""

from __future__ import annotations

from sqlmodel import select

from api.models.entities import AuditLog


def _bootstrap(client) -> int:
    project = client.post("/api/v1/projects", json={"name": "P"}).json()
    sp = client.post(
        f"/api/v1/projects/{project['id']}/subprojects",
        json={"name": "S"},
    ).json()
    ticket = client.post(
        f"/api/v1/subprojects/{sp['id']}/tickets", json={"title": "T"}
    ).json()
    return ticket["id"]


def test_valid_status_progression(client):
    ticket_id = _bootstrap(client)
    for new_status in ("IN_PROGRESS", "REVIEW", "DONE"):
        r = client.patch(f"/api/v1/tickets/{ticket_id}", json={"status": new_status})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == new_status


def test_invalid_status_returns_400(client):
    ticket_id = _bootstrap(client)
    r = client.patch(f"/api/v1/tickets/{ticket_id}", json={"status": "BOGUS"})
    # Pydantic validation yields 422 when the enum fails; treat both as "not 200".
    assert r.status_code in (400, 422)


def test_empty_patch_returns_400(client):
    ticket_id = _bootstrap(client)
    r = client.patch(f"/api/v1/tickets/{ticket_id}", json={})
    assert r.status_code == 400


def test_status_update_writes_audit_log(client, session):
    ticket_id = _bootstrap(client)
    client.patch(f"/api/v1/tickets/{ticket_id}", json={"status": "IN_PROGRESS"})

    logs = list(
        session.exec(select(AuditLog).where(AuditLog.ticket_id == ticket_id)).all()
    )
    assert len(logs) == 1
    assert logs[0].action.value == "STATUS_UPDATE"
    assert logs[0].actor.value == "HUMAN"


def test_agent_bearer_tags_actor_as_agent(client, session, agent_headers):
    ticket_id = _bootstrap(client)
    client.patch(
        f"/api/v1/tickets/{ticket_id}",
        json={"status": "IN_PROGRESS"},
        headers=agent_headers,
    )
    logs = list(
        session.exec(select(AuditLog).where(AuditLog.ticket_id == ticket_id)).all()
    )
    assert logs[-1].actor.value == "AGENT"
