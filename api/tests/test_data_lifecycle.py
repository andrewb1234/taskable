"""Tenant export, recoverable deletion, and verified purge coverage."""

from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from api.lifecycle import purge_workspace
from api.models.entities import (
    ApiKey,
    Project,
    Ticket,
    TicketDependency,
    Workspace,
    WorkspaceLifecycleEvent,
)
from api.models.enums import WorkspaceLifecycleAction
from api.utils.time import utcnow


def _headers(identity: str) -> dict[str, str]:
    return {"X-Test-User": identity}


def _create_graph(client, identity: str) -> dict[str, int | str]:
    headers = _headers(identity)
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": f"{identity} recovery project"},
    )
    assert project.status_code == 201, project.text
    project_payload = project.json()
    project_id = project_payload["id"]

    subproject = client.post(
        f"/api/v1/projects/{project_id}/subprojects",
        headers=headers,
        json={"name": "Recovery", "context_brief": "Tenant-only context"},
    )
    assert subproject.status_code == 201, subproject.text
    subproject_id = subproject.json()["id"]

    ticket = client.post(
        f"/api/v1/subprojects/{subproject_id}/tickets",
        headers=headers,
        json={"title": "Recover this ticket"},
    )
    assert ticket.status_code == 201, ticket.text
    ticket_id = ticket.json()["id"]
    comment = client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers=headers,
        json={"author": "HUMAN", "content": "Portable discussion"},
    )
    assert comment.status_code == 201, comment.text

    node = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        headers=headers,
        json={"title": "Recovery notes", "content": "Portable knowledge"},
    )
    assert node.status_code == 201, node.text
    proposal = client.post(
        f"/api/v1/knowledge/{node.json()['id']}/proposals",
        headers=headers,
        json={
            "proposed_changes": {"content": "Reviewed recovery notes"},
            "rationale": "Exercise export coverage",
        },
    )
    assert proposal.status_code == 201, proposal.text
    agent_session = client.post(
        f"/api/v1/projects/{project_id}/sessions",
        headers=headers,
        json={"intent": "Verify portable recovery"},
    )
    assert agent_session.status_code == 201, agent_session.text

    workspace = next(
        row
        for row in client.get(
            "/api/v1/workspaces",
            headers=headers,
        ).json()
        if row["id"] == project_payload["workspace_id"]
    )
    api_key = client.post(
        "/api/v1/apikeys",
        headers=headers,
        json={
            "name": f"{identity} recovery key",
            "workspace_id": workspace["id"],
            "scopes": ["read", "write"],
            "project_ids": [project_id],
        },
    )
    assert api_key.status_code == 200, api_key.text

    return {
        "workspace": workspace["id"],
        "workspace_slug": workspace["slug"],
        "project": project_id,
        "subproject": subproject_id,
        "ticket": ticket_id,
        "node": node.json()["id"],
        "api_key": api_key.json()["id"],
        "raw_api_key": api_key.json()["key"],
    }


def _export(client, graph, identity: str):
    response = client.get(
        f"/api/v1/workspaces/{graph['workspace']}/export",
        headers={
            **_headers(identity),
            "Origin": "http://localhost:5173",
        },
    )
    assert response.status_code == 200, response.text
    return response


def _schedule(client, graph, identity: str, sha256: str):
    return client.post(
        f"/api/v1/workspaces/{graph['workspace']}/deletion",
        headers=_headers(identity),
        json={
            "confirmation": graph["workspace_slug"],
            "export_sha256": sha256,
        },
    )


def test_export_is_complete_scoped_hashed_and_secret_free(
    multi_user_client,
):
    client, _ = multi_user_client
    alice = _create_graph(client, "alice")
    _create_graph(client, "bob")

    response = _export(client, alice, "alice")
    digest = hashlib.sha256(response.content).hexdigest()
    assert response.headers["x-mouvadah-export-sha256"] == digest
    assert response.headers["cache-control"] == "no-store"
    assert "attachment;" in response.headers["content-disposition"]
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "content-disposition" in exposed
    assert "x-mouvadah-export-sha256" in exposed

    payload = response.json()
    assert payload["format"] == "mouvadah.workspace-export.v1"
    assert payload["workspace"]["id"] == alice["workspace"]
    assert payload["record_counts"]["projects"] == 1
    assert payload["record_counts"]["tickets"] == 1
    assert payload["record_counts"]["comments"] == 1
    assert payload["record_counts"]["knowledge_nodes"] == 1
    assert payload["record_counts"]["knowledge_proposals"] == 1
    assert payload["record_counts"]["agent_sessions"] == 1
    assert payload["record_counts"]["api_keys"] == 1
    assert payload["tables"]["projects"][0]["name"].startswith("alice")
    assert all(
        row["workspace_id"] == alice["workspace"]
        for row in payload["tables"]["projects"]
    )
    assert "key_hash" not in response.text
    assert alice["raw_api_key"] not in response.text

    denied = client.get(
        f"/api/v1/workspaces/{alice['workspace']}/export",
        headers=_headers("bob"),
    )
    assert denied.status_code == 404

    events = client.get(
        f"/api/v1/workspaces/{alice['workspace']}/lifecycle-events",
        headers=_headers("alice"),
    )
    assert events.status_code == 200
    assert events.json()[-1]["action"] == "EXPORTED"
    assert events.json()[-1]["details"]["sha256"] == digest


def test_api_keys_cannot_export_or_control_workspace_deletion(
    enforce_auth_client,
    agent_headers,
):
    workspace = enforce_auth_client.get(
        "/api/v1/workspaces",
        headers=agent_headers,
    ).json()[0]

    response = enforce_auth_client.get(
        f"/api/v1/workspaces/{workspace['id']}/export",
        headers=agent_headers,
    )

    assert response.status_code == 403
    assert "interactive owner session" in response.json()["detail"]


def test_default_api_key_target_skips_deleted_workspace(multi_user_client):
    client, _ = multi_user_client
    graph = _create_graph(client, "alice")
    exported = _export(client, graph, "alice")
    assert _schedule(
        client,
        graph,
        "alice",
        exported.headers["x-mouvadah-export-sha256"],
    ).status_code == 200
    active = client.post(
        "/api/v1/workspaces",
        headers=_headers("alice"),
        json={"name": "Active recovery workspace"},
    )
    assert active.status_code == 201, active.text

    created = client.post(
        "/api/v1/apikeys",
        headers=_headers("alice"),
        json={"name": "active-default", "scopes": ["read", "write"]},
    )

    assert created.status_code == 200, created.text
    assert created.json()["workspace_id"] == active.json()["id"]


def test_deletion_requires_exact_slug_and_recent_matching_export(
    multi_user_client,
    engine,
):
    client, _ = multi_user_client
    graph = _create_graph(client, "alice")

    missing_export = _schedule(client, graph, "alice", "0" * 64)
    assert missing_export.status_code == 409

    exported = _export(client, graph, "alice")
    sha256 = exported.headers["x-mouvadah-export-sha256"]
    with Session(engine) as session:
        event = session.exec(
            select(WorkspaceLifecycleEvent)
            .where(
                WorkspaceLifecycleEvent.workspace_id == graph["workspace"],
                WorkspaceLifecycleEvent.action
                == WorkspaceLifecycleAction.EXPORTED,
            )
            .order_by(WorkspaceLifecycleEvent.id.desc())
        ).first()
        assert event is not None
        event.occurred_at = utcnow() - timedelta(hours=25)
        session.add(event)
        session.commit()
    stale_export = _schedule(client, graph, "alice", sha256)
    assert stale_export.status_code == 409

    exported = _export(client, graph, "alice")
    sha256 = exported.headers["x-mouvadah-export-sha256"]
    wrong_slug = client.post(
        f"/api/v1/workspaces/{graph['workspace']}/deletion",
        headers=_headers("alice"),
        json={"confirmation": "wrong", "export_sha256": sha256},
    )
    assert wrong_slug.status_code == 422
    assert sha256 != "0" * 64


def test_schedule_hides_workspace_graph_revokes_keys_and_restore_recovers(
    multi_user_client,
    engine,
):
    client, _ = multi_user_client
    graph = _create_graph(client, "alice")
    exported = _export(client, graph, "alice")

    scheduled = _schedule(
        client,
        graph,
        "alice",
        exported.headers["x-mouvadah-export-sha256"],
    )

    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["revoked_api_keys"] == 1
    assert client.get(
        "/api/v1/projects",
        headers=_headers("alice"),
    ).json() == []
    assert client.get(
        f"/api/v1/projects/{graph['project']}",
        headers=_headers("alice"),
    ).status_code == 404
    listed_workspace = client.get(
        "/api/v1/workspaces",
        headers=_headers("alice"),
    ).json()[0]
    assert listed_workspace["deletion_requested_at"] is not None
    assert listed_workspace["purge_after"] is not None

    with Session(engine) as session:
        api_key = session.get(ApiKey, graph["api_key"])
        assert api_key is not None
        assert api_key.revoked is True

    restored = client.post(
        f"/api/v1/workspaces/{graph['workspace']}/restore",
        headers=_headers("alice"),
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["deletion_requested_at"] is None
    assert len(
        client.get("/api/v1/projects", headers=_headers("alice")).json()
    ) == 1
    with Session(engine) as session:
        api_key = session.get(ApiKey, graph["api_key"])
        assert api_key is not None
        assert api_key.revoked is True

    actions = [
        event["action"]
        for event in client.get(
            f"/api/v1/workspaces/{graph['workspace']}/lifecycle-events",
            headers=_headers("alice"),
        ).json()
    ]
    assert actions == [
        "EXPORTED",
        "DELETION_SCHEDULED",
        "DELETION_RESTORED",
    ]


def test_expired_deletion_cannot_be_restored(multi_user_client, engine):
    client, _ = multi_user_client
    graph = _create_graph(client, "alice")
    exported = _export(client, graph, "alice")
    assert _schedule(
        client,
        graph,
        "alice",
        exported.headers["x-mouvadah-export-sha256"],
    ).status_code == 200

    with Session(engine) as session:
        workspace = session.get(Workspace, graph["workspace"])
        assert workspace is not None
        now = utcnow()
        workspace.deletion_requested_at = now - timedelta(seconds=2)
        workspace.purge_after = now - timedelta(seconds=1)
        session.add(workspace)
        session.commit()

    response = client.post(
        f"/api/v1/workspaces/{graph['workspace']}/restore",
        headers=_headers("alice"),
    )
    assert response.status_code == 409
    assert "expired" in response.json()["detail"]


def test_verified_purge_removes_one_tenant_and_retains_ledger(
    multi_user_client,
    engine,
):
    client, _ = multi_user_client
    alice = _create_graph(client, "alice")
    bob = _create_graph(client, "bob")
    exported = _export(client, alice, "alice")
    assert _schedule(
        client,
        alice,
        "alice",
        exported.headers["x-mouvadah-export-sha256"],
    ).status_code == 200

    with Session(engine) as session:
        # A corrupt or legacy cross-workspace edge must not block purge or
        # cause the retained record count to disagree with the actual sweep.
        session.add(
            TicketDependency(
                ticket_id=alice["ticket"],
                depends_on_ticket_id=bob["ticket"],
            )
        )
        workspace = session.get(Workspace, alice["workspace"])
        assert workspace is not None
        now = utcnow()
        workspace.deletion_requested_at = now - timedelta(seconds=2)
        workspace.purge_after = now - timedelta(seconds=1)
        session.add(workspace)
        session.commit()

    with Session(engine) as session:
        with pytest.raises(ValueError, match="backup evidence"):
            purge_workspace(
                session,
                int(alice["workspace"]),
                backup_evidence="",
            )
        result = purge_workspace(
            session,
            int(alice["workspace"]),
            backup_evidence="s3://verified/backup#etag=abc123",
        )
        assert result.deleted_records["projects"] == 1
        assert result.deleted_records["tickets"] == 1
        assert result.deleted_records["ticket_dependencies"] == 1
        assert session.get(Workspace, alice["workspace"]) is None
        assert session.get(Project, alice["project"]) is None
        assert session.get(Workspace, bob["workspace"]) is not None
        assert session.get(Project, bob["project"]) is not None
        assert session.get(Ticket, bob["ticket"]) is not None
        assert (
            session.exec(select(TicketDependency)).first()
            is None
        )
        purged = session.exec(
            select(WorkspaceLifecycleEvent).where(
                WorkspaceLifecycleEvent.workspace_id == alice["workspace"],
                WorkspaceLifecycleEvent.action
                == WorkspaceLifecycleAction.PURGED,
            )
        ).one()
        assert "s3://verified/backup" in purged.details["backup_evidence"]
        assert purged.details["deleted_records"]["knowledge_nodes"] == 1
