"""Workspace object-level authorization and isolation tests."""

from __future__ import annotations

from sqlmodel import Session, select

from api.authorization import ensure_personal_workspace
from api.events import Event
from api.models.entities import Project, User, WorkspaceMembership
from api.models.enums import SSEAction, WorkspaceRole
from api.routes.events import can_receive_event


def _headers(identity: str) -> dict[str, str]:
    return {"X-Test-User": identity}


def _create_graph(client, identity: str) -> dict[str, int]:
    headers = _headers(identity)
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": f"{identity} project"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    workspace_id = project.json()["workspace_id"]

    subproject = client.post(
        f"/api/v1/projects/{project_id}/subprojects",
        headers=headers,
        json={"name": "Delivery", "context_brief": "Private plan"},
    )
    assert subproject.status_code == 201, subproject.text
    subproject_id = subproject.json()["id"]

    ticket = client.post(
        f"/api/v1/subprojects/{subproject_id}/tickets",
        headers=headers,
        json={"title": "Private ticket"},
    )
    assert ticket.status_code == 201, ticket.text
    ticket_id = ticket.json()["id"]

    comment = client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers=headers,
        json={"author": "HUMAN", "content": "Private discussion"},
    )
    assert comment.status_code == 201, comment.text

    node = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        headers=headers,
        json={"title": "Private knowledge", "content": "Secret context"},
    )
    assert node.status_code == 201, node.text
    node_id = node.json()["id"]

    proposal = client.post(
        f"/api/v1/knowledge/{node_id}/proposals",
        headers=headers,
        json={
            "proposed_changes": {"content": "Revised secret"},
            "rationale": "Test",
        },
    )
    assert proposal.status_code == 201, proposal.text

    agent_session = client.post(
        f"/api/v1/projects/{project_id}/sessions",
        headers=headers,
        json={"intent": "Private work", "loaded_node_ids": [node_id]},
    )
    assert agent_session.status_code == 201, agent_session.text

    return {
        "workspace": workspace_id,
        "project": project_id,
        "subproject": subproject_id,
        "ticket": ticket_id,
        "node": node_id,
        "proposal": proposal.json()["id"],
        "session": agent_session.json()["id"],
    }


def test_project_lists_and_direct_ids_are_workspace_scoped(multi_user_client):
    client, _ = multi_user_client
    alice = _create_graph(client, "alice")

    assert len(client.get("/api/v1/projects", headers=_headers("alice")).json()) == 1
    assert client.get("/api/v1/projects", headers=_headers("bob")).json() == []

    for method in ("get", "delete"):
        response = getattr(client, method)(
            f"/api/v1/projects/{alice['project']}",
            headers=_headers("bob"),
        )
        assert response.status_code == 404


def test_descendant_and_agent_routes_reject_cross_workspace_ids(
    multi_user_client,
):
    client, _ = multi_user_client
    alice = _create_graph(client, "alice")
    bob_headers = _headers("bob")

    reads = [
        f"/api/v1/projects/{alice['project']}/tickets",
        f"/api/v1/projects/{alice['project']}/subprojects",
        f"/api/v1/subprojects/{alice['subproject']}",
        f"/api/v1/tickets/{alice['ticket']}",
        f"/api/v1/tickets/{alice['ticket']}/comments",
        f"/api/v1/projects/{alice['project']}/knowledge",
        f"/api/v1/projects/{alice['project']}/knowledge/context-trail?query=private",
        f"/api/v1/knowledge/{alice['node']}",
        f"/api/v1/knowledge/{alice['node']}/proposals",
        f"/api/v1/tickets/knowledge/{alice['node']}/tickets",
        f"/api/v1/projects/{alice['project']}/knowledge/proposals",
        f"/api/v1/projects/{alice['project']}/sessions",
        f"/api/v1/agent/sessions/{alice['session']}",
        f"/api/v1/agent/context/{alice['subproject']}",
        f"/api/v1/agent/projects/{alice['project']}/knowledge",
        f"/api/v1/agent/projects/{alice['project']}/context-trail?query=private",
        f"/api/v1/agent/knowledge/{alice['node']}",
    ]
    for path in reads:
        response = client.get(path, headers=bob_headers)
        assert response.status_code == 404, (path, response.text)

    writes = [
        (
            "patch",
            f"/api/v1/subprojects/{alice['subproject']}",
            {"name": "stolen"},
        ),
        (
            "post",
            f"/api/v1/subprojects/{alice['subproject']}/tickets",
            {"title": "stolen"},
        ),
        (
            "patch",
            f"/api/v1/tickets/{alice['ticket']}",
            {"title": "stolen"},
        ),
        (
            "post",
            f"/api/v1/tickets/{alice['ticket']}/comments",
            {"author": "HUMAN", "content": "stolen"},
        ),
        (
            "post",
            f"/api/v1/tickets/{alice['ticket']}/claim",
            {"worker_id": "bob-worker"},
        ),
        (
            "post",
            f"/api/v1/tickets/{alice['ticket']}/heartbeat",
            {"worker_id": "bob-worker"},
        ),
        (
            "post",
            f"/api/v1/tickets/subprojects/{alice['subproject']}/requeue-expired",
            {},
        ),
        (
            "post",
            f"/api/v1/tickets/{alice['ticket']}/mr",
            {"url": "https://example.com/stolen"},
        ),
        (
            "post",
            f"/api/v1/projects/{alice['project']}/knowledge",
            {"title": "stolen"},
        ),
        (
            "patch",
            f"/api/v1/knowledge/{alice['node']}",
            {"title": "stolen"},
        ),
        (
            "post",
            f"/api/v1/knowledge/{alice['node']}/proposals",
            {"proposed_changes": {"title": "stolen"}},
        ),
        (
            "patch",
            f"/api/v1/knowledge/proposals/{alice['proposal']}",
            {"action": "accept", "reviewed_by": "Bob"},
        ),
        (
            "post",
            f"/api/v1/projects/{alice['project']}/sessions",
            {"intent": "stolen"},
        ),
        (
            "patch",
            f"/api/v1/agent/sessions/{alice['session']}",
            {"status": "COMPLETE"},
        ),
    ]
    for method, path, payload in writes:
        response = getattr(client, method)(
            path,
            headers=bob_headers,
            json=payload,
        )
        assert response.status_code == 404, (path, response.text)

    deletes = [
        f"/api/v1/subprojects/{alice['subproject']}",
        f"/api/v1/tickets/{alice['ticket']}",
        f"/api/v1/knowledge/{alice['node']}",
    ]
    for path in deletes:
        response = client.delete(path, headers=bob_headers)
        assert response.status_code == 404, (path, response.text)


def test_cross_workspace_dependencies_and_refs_are_not_enumerable(
    multi_user_client,
):
    client, _ = multi_user_client
    alice = _create_graph(client, "alice")
    bob = _create_graph(client, "bob")

    dependency = client.patch(
        f"/api/v1/tickets/{bob['ticket']}",
        headers=_headers("bob"),
        json={"depends_on": [alice["ticket"]]},
    )
    assert dependency.status_code == 422
    assert "not found" in dependency.json()["detail"]

    parent = client.post(
        f"/api/v1/projects/{bob['project']}/knowledge",
        headers=_headers("bob"),
        json={"title": "Bad child", "parent_id": alice["node"]},
    )
    assert parent.status_code == 400
    assert "does not exist" in parent.json()["detail"]

    loaded_nodes = client.post(
        f"/api/v1/projects/{bob['project']}/sessions",
        headers=_headers("bob"),
        json={"intent": "Bad context", "loaded_node_ids": [alice["node"]]},
    )
    assert loaded_nodes.status_code == 422
    assert "unknown project node" in loaded_nodes.json()["detail"]


def test_viewer_can_read_but_cannot_mutate(multi_user_client, engine):
    client, users = multi_user_client
    alice = _create_graph(client, "alice")

    with Session(engine) as session:
        session.add(
            WorkspaceMembership(
                workspace_id=alice["workspace"],
                user_id=users["bob"].id,
                role=WorkspaceRole.VIEWER,
            )
        )
        session.commit()

    readable = client.get(
        f"/api/v1/tickets/{alice['ticket']}",
        headers=_headers("bob"),
    )
    assert readable.status_code == 200

    denied = client.patch(
        f"/api/v1/tickets/{alice['ticket']}",
        headers=_headers("bob"),
        json={"title": "viewer edit"},
    )
    assert denied.status_code == 404

    denied_delete = client.delete(
        f"/api/v1/projects/{alice['project']}",
        headers=_headers("bob"),
    )
    assert denied_delete.status_code == 404


def test_workspace_member_listing_is_admin_only(multi_user_client, engine):
    client, users = multi_user_client
    alice = _create_graph(client, "alice")

    with Session(engine) as session:
        session.add(
            WorkspaceMembership(
                workspace_id=alice["workspace"],
                user_id=users["bob"].id,
                role=WorkspaceRole.MEMBER,
            )
        )
        session.commit()

    owner_response = client.get(
        f"/api/v1/workspaces/{alice['workspace']}/members",
        headers=_headers("alice"),
    )
    assert owner_response.status_code == 200
    assert {member["email"] for member in owner_response.json()} == {
        "alice@example.com",
        "bob@example.com",
    }

    member_response = client.get(
        f"/api/v1/workspaces/{alice['workspace']}/members",
        headers=_headers("bob"),
    )
    assert member_response.status_code == 404


def test_realtime_event_membership_is_checked_at_delivery(
    multi_user_client,
    engine,
):
    client, users = multi_user_client
    alice = _create_graph(client, "alice")
    event = Event(
        action=SSEAction.TICKET_UPDATED,
        entity="ticket",
        entity_id=alice["ticket"],
        workspace_id=alice["workspace"],
    )

    with Session(engine) as session:
        assert can_receive_event(session, users["alice"], event) is True
        assert can_receive_event(session, users["bob"], event) is False
        membership = WorkspaceMembership(
            workspace_id=alice["workspace"],
            user_id=users["bob"].id,
            role=WorkspaceRole.MEMBER,
        )
        session.add(membership)
        session.commit()
        assert can_receive_event(session, users["bob"], event) is True
        session.delete(membership)
        session.commit()
        assert can_receive_event(session, users["bob"], event) is False
def test_sole_local_user_safely_adopts_legacy_projects(engine):
    with Session(engine) as session:
        user = User(
            google_id="legacy-owner",
            email="owner@example.com",
            name="Owner",
        )
        project = Project(name="Legacy", workspace_id=None)
        session.add(user)
        session.add(project)
        session.commit()
        session.refresh(user)
        session.refresh(project)

        workspace = ensure_personal_workspace(session, user)
        session.refresh(project)

        assert project.workspace_id == workspace.id
        membership = session.exec(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace.id,
                WorkspaceMembership.user_id == user.id,
            )
        ).one()
        assert membership.role == WorkspaceRole.OWNER


def test_multi_user_database_does_not_guess_legacy_owner(engine):
    with Session(engine) as session:
        alice = User(
            google_id="legacy-alice",
            email="alice@example.com",
            name="Alice",
        )
        bob = User(
            google_id="legacy-bob",
            email="bob@example.com",
            name="Bob",
        )
        project = Project(name="Unclaimed legacy", workspace_id=None)
        session.add_all([alice, bob, project])
        session.commit()
        session.refresh(alice)
        session.refresh(project)

        ensure_personal_workspace(session, alice)
        session.refresh(project)

        assert project.workspace_id is None


def test_explicit_legacy_owner_can_adopt_in_multi_user_database(
    engine,
    monkeypatch,
):
    monkeypatch.setenv("LEGACY_OWNER_EMAIL", "alice@example.com")
    from api.config import get_settings

    get_settings.cache_clear()
    with Session(engine) as session:
        alice = User(
            google_id="explicit-alice",
            email="alice@example.com",
            name="Alice",
        )
        bob = User(
            google_id="explicit-bob",
            email="bob@example.com",
            name="Bob",
        )
        project = Project(name="Explicit legacy", workspace_id=None)
        session.add_all([alice, bob, project])
        session.commit()
        session.refresh(alice)
        session.refresh(project)

        workspace = ensure_personal_workspace(session, alice)
        session.refresh(project)

        assert project.workspace_id == workspace.id
