"""Tests for the bounded project Control Room read model."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.events import Event, get_broadcaster
from api.models.enums import SSEAction


def _make_project(client: TestClient) -> tuple[int, int, int]:
    project = client.post(
        "/api/v1/projects",
        json={"name": "Control room", "description": "Operational state"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    first = client.post(
        f"/api/v1/projects/{project_id}/subprojects",
        json={"name": "First", "context_brief": "First brief"},
    )
    second = client.post(
        f"/api/v1/projects/{project_id}/subprojects",
        json={"name": "Second", "context_brief": "Second brief"},
    )
    assert first.status_code == second.status_code == 201
    return project_id, first.json()["id"], second.json()["id"]


def _ticket(
    client: TestClient,
    subproject_id: int,
    title: str,
    *,
    status: str,
    assignee: str = "UNASSIGNED",
) -> dict:
    response = client.post(
        f"/api/v1/subprojects/{subproject_id}/tickets",
        json={"title": title, "status": status, "assignee": assignee},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_control_room_summary_is_compact_and_aggregates_project_state(
    client: TestClient,
):
    project_id, first_id, second_id = _make_project(client)
    blocked = _ticket(
        client,
        first_id,
        "Resolve blocker",
        status="BLOCKED",
        assignee="HUMAN",
    )
    review = _ticket(
        client,
        first_id,
        "Review evidence",
        status="REVIEW",
        assignee="AGENT",
    )
    in_flight = _ticket(
        client,
        second_id,
        "Ship summary endpoint",
        status="IN_PROGRESS",
        assignee="AGENT",
    )
    _ticket(client, second_id, "Deferred task", status="TODO")

    oversized_content = "private knowledge body " * 2_000
    node = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={"title": "Historical evidence", "content": oversized_content},
    )
    assert node.status_code == 201, node.text
    node_id = node.json()["id"]
    stale = client.patch(
        f"/api/v1/knowledge/{node_id}", json={"status": "STALE"}
    )
    assert stale.status_code == 200, stale.text
    proposal = client.post(
        f"/api/v1/knowledge/{node_id}/proposals",
        json={"proposed_changes": {"content": "A revised private body"}},
    )
    assert proposal.status_code == 201, proposal.text

    session = client.post(
        f"/api/v1/projects/{project_id}/sessions",
        json={"intent": "Resume delivery", "loaded_node_ids": [node_id]},
    )
    assert session.status_code == 201, session.text
    interrupted = client.patch(
        f"/api/v1/agent/sessions/{session.json()['id']}",
        json={
            "status": "INTERRUPTED",
            "handoff_note": "Continue from the verified control-room work.",
        },
    )
    assert interrupted.status_code == 200, interrupted.text

    response = client.get(f"/api/v1/projects/{project_id}/control-room")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project"]["id"] == project_id
    assert [subproject["id"] for subproject in body["subprojects"]] == [
        first_id,
        second_id,
    ]
    assert body["subprojects"][0]["context_preview"] == "First brief"
    assert "context_brief" not in body["subprojects"][0]
    assert body["ticket_status_counts"] == {
        "TODO": 1,
        "IN_PROGRESS": 1,
        "BLOCKED": 1,
        "REVIEW": 1,
        "DONE": 0,
    }
    assert body["ticket_assignee_counts"] == {
        "HUMAN": 1,
        "AGENT": 2,
        "UNASSIGNED": 1,
    }
    assert [ticket["id"] for ticket in body["attention_tickets"]] == [
        blocked["id"],
        review["id"],
    ]
    assert body["attention_total"] == 2
    assert [ticket["id"] for ticket in body["in_flight_tickets"]] == [
        in_flight["id"]
    ]
    assert body["in_flight_total"] == 1
    assert body["stale_knowledge_count"] == 1
    assert body["pending_proposal_count"] == 1
    assert [item["intent"] for item in body["resumable_sessions"]] == [
        "Resume delivery"
    ]
    assert oversized_content not in response.text
    assert "proposed_changes" not in response.text

    counts = {item["subproject_id"]: item for item in body["subproject_ticket_counts"]}
    assert counts[first_id] == {
        "subproject_id": first_id,
        "total": 2,
        "moving": 0,
        "attention": 2,
    }
    assert counts[second_id] == {
        "subproject_id": second_id,
        "total": 2,
        "moving": 1,
        "attention": 0,
    }


def test_control_room_summary_bounds_focal_ticket_lists(client: TestClient):
    project_id, first_id, _ = _make_project(client)
    for index in range(21):
        _ticket(
            client,
            first_id,
            f"Review {index}",
            status="REVIEW",
        )
    for index in range(21):
        _ticket(
            client,
            first_id,
            f"In flight {index}",
            status="IN_PROGRESS",
        )

    response = client.get(f"/api/v1/projects/{project_id}/control-room")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["attention_total"] == 21
    assert len(body["attention_tickets"]) == 20
    assert body["in_flight_total"] == 21
    assert len(body["in_flight_tickets"]) == 20


def test_control_room_summary_bounds_subproject_context_previews(
    client: TestClient,
):
    project_id, first_id, _ = _make_project(client)
    oversized_brief = "bounded context " * 200
    update = client.patch(
        f"/api/v1/subprojects/{first_id}",
        json={"context_brief": oversized_brief},
    )
    assert update.status_code == 200, update.text

    response = client.get(f"/api/v1/projects/{project_id}/control-room")

    assert response.status_code == 200, response.text
    preview = response.json()["subprojects"][0]["context_preview"]
    assert preview == oversized_brief[:280]
    assert len(preview) == 280
    assert oversized_brief not in response.text


def test_proposal_review_event_is_project_scoped(client: TestClient):
    project_id, first_id, _ = _make_project(client)
    del first_id
    node = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={"title": "Review target"},
    )
    assert node.status_code == 201, node.text
    proposal = client.post(
        f"/api/v1/knowledge/{node.json()['id']}/proposals",
        json={"proposed_changes": {"title": "Reviewed target"}},
    )
    assert proposal.status_code == 201, proposal.text

    captured: list[Event] = []
    broadcaster = get_broadcaster()
    original_publish = broadcaster.publish

    async def capture(event: Event) -> None:
        captured.append(event)
        await original_publish(event)

    broadcaster.publish = capture  # type: ignore[assignment]
    try:
        response = client.patch(
            f"/api/v1/knowledge/proposals/{proposal.json()['id']}",
            json={"action": "reject"},
        )
    finally:
        broadcaster.publish = original_publish  # type: ignore[assignment]

    assert response.status_code == 200, response.text
    reviewed = next(
        event
        for event in captured
        if event.action is SSEAction.KNOWLEDGE_PROPOSAL_REVIEWED
    )
    assert reviewed.parent_id == project_id
