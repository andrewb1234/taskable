"""Happy-path CRUD across Project → Subproject → Ticket → Comment."""

from __future__ import annotations


def test_project_creation_and_listing(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": "Taskable Core", "description": "MVP sprint."},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["name"] == "Taskable Core"

    listed = client.get("/api/v1/projects").json()
    assert len(listed) == 1
    assert listed[0]["id"] == data["id"]


def test_subproject_assignment_and_detail(client):
    project = client.post("/api/v1/projects", json={"name": "P"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/subprojects",
        json={"name": "Sprint 1", "context_brief": "Ship the kanban MVP."},
    )
    assert response.status_code == 201
    sp = response.json()
    assert sp["project_id"] == project["id"]
    assert sp["status"] == "PLANNING"
    assert sp["context_brief"] == "Ship the kanban MVP."

    detail = client.get(f"/api/v1/subprojects/{sp['id']}").json()
    assert detail["tickets"] == []
    assert detail["name"] == "Sprint 1"


def test_ticket_generation_with_defaults(client):
    project = client.post("/api/v1/projects", json={"name": "P"}).json()
    sp = client.post(
        f"/api/v1/projects/{project['id']}/subprojects",
        json={"name": "S", "context_brief": ""},
    ).json()

    response = client.post(
        f"/api/v1/subprojects/{sp['id']}/tickets",
        json={"title": "Wire the API", "description": "FastAPI routes."},
    )
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["status"] == "TODO"
    assert ticket["assignee"] == "UNASSIGNED"

    detail = client.get(f"/api/v1/subprojects/{sp['id']}").json()
    assert len(detail["tickets"]) == 1


def test_comment_thread_round_trip(client):
    project = client.post("/api/v1/projects", json={"name": "P"}).json()
    sp = client.post(
        f"/api/v1/projects/{project['id']}/subprojects",
        json={"name": "S"},
    ).json()
    ticket = client.post(
        f"/api/v1/subprojects/{sp['id']}/tickets",
        json={"title": "T"},
    ).json()

    posted = client.post(
        f"/api/v1/tickets/{ticket['id']}/comments",
        json={"author": "HUMAN", "content": "Kicking off."},
    )
    assert posted.status_code == 201
    assert posted.json()["author"] == "HUMAN"

    listed = client.get(f"/api/v1/tickets/{ticket['id']}/comments").json()
    assert len(listed) == 1
    assert listed[0]["content"] == "Kicking off."


def test_nonexistent_parent_returns_404(client):
    assert client.get("/api/v1/projects/999").status_code == 404
    assert client.get("/api/v1/subprojects/999").status_code == 404
    assert client.get("/api/v1/tickets/999").status_code == 404
    assert (
        client.post(
            "/api/v1/subprojects/999/tickets", json={"title": "x"}
        ).status_code
        == 404
    )
