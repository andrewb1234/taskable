"""Delete endpoints for projects, subprojects, tickets.

Covers cascade behavior (deleting a parent sweeps its children) and the
SSE events that get published for each deletion.
"""

from __future__ import annotations

from api.events import get_broadcaster


def _seed(client) -> dict:
    """Return ids for a fully populated project → subproject → ticket → node tree."""
    project = client.post("/api/v1/projects", json={"name": "P"}).json()
    sub = client.post(
        f"/api/v1/projects/{project['id']}/subprojects",
        json={"name": "S", "context_brief": "brief"},
    ).json()
    ticket = client.post(
        f"/api/v1/subprojects/{sub['id']}/tickets",
        json={"title": "T", "description": "d"},
    ).json()
    node = client.post(
        f"/api/v1/projects/{project['id']}/knowledge",
        json={"title": "N", "node_type": "RAW", "content": "x"},
    ).json()
    return {
        "project_id": project["id"],
        "subproject_id": sub["id"],
        "ticket_id": ticket["id"],
        "node_id": node["id"],
    }


def test_delete_ticket_removes_ticket_only(client):
    ids = _seed(client)
    response = client.delete(f"/api/v1/tickets/{ids['ticket_id']}")
    assert response.status_code == 204

    # Ticket is gone, subproject and project remain.
    assert client.get(f"/api/v1/tickets/{ids['ticket_id']}").status_code == 404
    assert (
        client.get(f"/api/v1/subprojects/{ids['subproject_id']}").status_code == 200
    )
    assert client.get(f"/api/v1/projects/{ids['project_id']}").status_code == 200


def test_delete_subproject_cascades_tickets(client):
    ids = _seed(client)
    response = client.delete(f"/api/v1/subprojects/{ids['subproject_id']}")
    assert response.status_code == 204

    # Subproject and its tickets are gone.
    assert (
        client.get(f"/api/v1/subprojects/{ids['subproject_id']}").status_code == 404
    )
    assert client.get(f"/api/v1/tickets/{ids['ticket_id']}").status_code == 404

    # The parent project survives.
    assert client.get(f"/api/v1/projects/{ids['project_id']}").status_code == 200


def test_delete_project_cascades_entire_tree(client):
    ids = _seed(client)
    response = client.delete(f"/api/v1/projects/{ids['project_id']}")
    assert response.status_code == 204

    assert client.get(f"/api/v1/projects/{ids['project_id']}").status_code == 404
    assert (
        client.get(f"/api/v1/subprojects/{ids['subproject_id']}").status_code == 404
    )
    assert client.get(f"/api/v1/tickets/{ids['ticket_id']}").status_code == 404
    # Knowledge nodes cascaded too.
    assert client.get(f"/api/v1/knowledge/{ids['node_id']}").status_code == 404


def test_delete_nonexistent_returns_404(client):
    assert client.delete("/api/v1/projects/999").status_code == 404
    assert client.delete("/api/v1/subprojects/999").status_code == 404
    assert client.delete("/api/v1/tickets/999").status_code == 404


def test_delete_emits_sse_events(client):
    """Each delete route pushes its matching SSEAction."""
    from api.events import Event

    ids = _seed(client)
    broadcaster = get_broadcaster()
    captured: list[Event] = []
    original_publish = broadcaster.publish

    async def capturing_publish(event: Event) -> None:
        captured.append(event)
        await original_publish(event)

    broadcaster.publish = capturing_publish  # type: ignore[assignment]
    try:
        client.delete(f"/api/v1/tickets/{ids['ticket_id']}")
        client.delete(f"/api/v1/subprojects/{ids['subproject_id']}")
        client.delete(f"/api/v1/projects/{ids['project_id']}")
    finally:
        broadcaster.publish = original_publish  # type: ignore[assignment]

    actions = [e.action.value for e in captured]
    assert "TICKET_DELETED" in actions
    assert "SUBPROJECT_DELETED" in actions
    assert "PROJECT_DELETED" in actions
