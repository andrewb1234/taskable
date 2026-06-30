"""Knowledge tree: CRUD, tree integrity, SSE, and agent outline."""

from __future__ import annotations

from api.events import Event, get_broadcaster
from api.models.enums import SSEAction


def _new_project(client, headers=None) -> int:
    return client.post("/api/v1/projects", json={"name": "P"}, headers=headers).json()["id"]


def test_knowledge_node_crud_roundtrip(client):
    project_id = _new_project(client)

    created = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={
            "title": "README.md",
            "node_type": "RAW",
            "content": "# Taskable\n\nshared state machine...",
            "source_refs": ["/absolute/path/README.md"],
        },
    )
    assert created.status_code == 201
    node = created.json()
    assert node["project_id"] == project_id
    assert node["parent_id"] is None
    assert node["node_type"] == "RAW"
    assert node["source_refs"] == ["/absolute/path/README.md"]
    assert node["created_by"] == "HUMAN"  # no bearer → tagged as human

    listed = client.get(f"/api/v1/projects/{project_id}/knowledge").json()
    assert [n["id"] for n in listed] == [node["id"]]

    fetched = client.get(f"/api/v1/knowledge/{node['id']}").json()
    assert fetched["content"].startswith("# Taskable")

    patched = client.patch(
        f"/api/v1/knowledge/{node['id']}",
        json={"title": "README (v2)", "node_type": "SUMMARY"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "README (v2)"
    assert patched.json()["node_type"] == "SUMMARY"

    deleted = client.delete(f"/api/v1/knowledge/{node['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/knowledge/{node['id']}").status_code == 404


def test_knowledge_node_tree_hierarchy(client):
    project_id = _new_project(client)

    parent = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={"title": "Architecture overview", "node_type": "SUMMARY"},
    ).json()

    child_a = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={
            "title": "api/main.py",
            "node_type": "RAW",
            "parent_id": parent["id"],
        },
    ).json()
    child_b = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={
            "title": "api/routes/projects.py",
            "node_type": "RAW",
            "parent_id": parent["id"],
        },
    ).json()

    nodes = client.get(f"/api/v1/projects/{project_id}/knowledge").json()
    parent_ids = {n["id"]: n["parent_id"] for n in nodes}
    assert parent_ids[child_a["id"]] == parent["id"]
    assert parent_ids[child_b["id"]] == parent["id"]

    # Deleting the parent cascades to its children.
    assert client.delete(f"/api/v1/knowledge/{parent['id']}").status_code == 204
    remaining = client.get(f"/api/v1/projects/{project_id}/knowledge").json()
    assert remaining == []


def test_knowledge_node_parent_must_be_same_project(client):
    p1 = _new_project(client)
    p2 = _new_project(client)
    foreign = client.post(
        f"/api/v1/projects/{p1}/knowledge",
        json={"title": "Foreign"},
    ).json()

    response = client.post(
        f"/api/v1/projects/{p2}/knowledge",
        json={"title": "Child", "parent_id": foreign["id"]},
    )
    assert response.status_code == 400
    assert "different project" in response.json()["detail"]


def test_knowledge_node_parent_cycle_rejected(client):
    project_id = _new_project(client)
    a = client.post(
        f"/api/v1/projects/{project_id}/knowledge", json={"title": "A"}
    ).json()
    b = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={"title": "B", "parent_id": a["id"]},
    ).json()

    # Trying to set A.parent = B would form a cycle A→B→A.
    response = client.patch(
        f"/api/v1/knowledge/{a['id']}",
        json={"parent_id": b["id"]},
    )
    assert response.status_code == 400
    assert "cycle" in response.json()["detail"]


def test_knowledge_mutations_emit_sse_events(client):
    project_id = _new_project(client)

    captured: list[Event] = []
    broadcaster = get_broadcaster()
    original_publish = broadcaster.publish

    async def capturing(event: Event) -> None:
        captured.append(event)
        await original_publish(event)

    broadcaster.publish = capturing  # type: ignore[assignment]
    try:
        node = client.post(
            f"/api/v1/projects/{project_id}/knowledge",
            json={"title": "A"},
        ).json()
        client.patch(
            f"/api/v1/knowledge/{node['id']}", json={"content": "hello"}
        )
        client.delete(f"/api/v1/knowledge/{node['id']}")
    finally:
        broadcaster.publish = original_publish  # type: ignore[assignment]

    actions = [event.action for event in captured]
    assert SSEAction.KNOWLEDGE_NODE_CREATED in actions
    assert SSEAction.KNOWLEDGE_NODE_UPDATED in actions
    assert SSEAction.KNOWLEDGE_NODE_DELETED in actions


def test_agent_knowledge_map_is_hierarchical(client, agent_headers):
    project_id = _new_project(client)
    parent = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={"title": "Stack", "node_type": "SUMMARY"},
    ).json()
    child = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={
            "title": "README.md",
            "node_type": "RAW",
            "parent_id": parent["id"],
            "source_refs": ["/abs/README.md"],
        },
    ).json()

    response = client.get(
        f"/api/v1/agent/projects/{project_id}/knowledge",
        headers=agent_headers,
    )
    assert response.status_code == 200
    body = response.text
    # Parent line precedes (and is outdented relative to) child line.
    parent_line = f"- [SUMMARY #{parent['id']}] Stack"
    child_line = f"  - [RAW #{child['id']}] README.md"
    assert parent_line in body
    assert child_line in body
    assert body.index(parent_line) < body.index(child_line)
    assert "/abs/README.md" in body


def test_agent_knowledge_node_read_requires_bearer(enforce_auth_client, agent_headers):
    project_id = _new_project(enforce_auth_client, agent_headers)
    node = enforce_auth_client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={"title": "N", "content": "body text"},
        headers=agent_headers,
    ).json()

    assert enforce_auth_client.get(f"/api/v1/agent/knowledge/{node['id']}").status_code == 401

    response = enforce_auth_client.get(
        f"/api/v1/agent/knowledge/{node['id']}",
        headers=agent_headers,
    )
    assert response.status_code == 200
    assert "body text" in response.text


def test_agent_endpoint_tags_created_by_agent(client, agent_headers):
    project_id = _new_project(client)
    node = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={"title": "Agent-authored"},
        headers=agent_headers,
    ).json()
    assert node["created_by"] == "AGENT"


def test_context_trail_finds_relevant_branch_and_load_order(client):
    project_id = _new_project(client)
    root = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={
            "title": "Game systems",
            "node_type": "SUMMARY",
            "content": "Top-level gameplay architecture and subsystem map.",
        },
    ).json()
    battle = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={
            "title": "Battle system",
            "node_type": "SUMMARY",
            "parent_id": root["id"],
            "content": "Use this when working on combat UI, turn order, damage preview, or status effects.",
        },
    ).json()
    damage = client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={
            "title": "Damage formula",
            "node_type": "RAW",
            "parent_id": battle["id"],
            "content": "Battle damage preview uses attack minus defense with elemental modifiers.",
            "source_refs": ["game/battle/damage.ts"],
        },
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={
            "title": "Save system",
            "node_type": "SUMMARY",
            "parent_id": root["id"],
            "content": "Save files, checkpoints, and profile slots.",
        },
    )

    response = client.get(
        f"/api/v1/projects/{project_id}/knowledge/context-trail",
        params={"query": "battle damage component"},
    )
    assert response.status_code == 200
    body = response.json()

    load_ids = [node["id"] for node in body["load_order"]]
    assert root["id"] in load_ids
    assert battle["id"] in load_ids
    assert any(item["id"] == damage["id"] for item in body["items"])

    battle_item = next(item for item in body["items"] if item["id"] == battle["id"])
    assert [part["title"] for part in battle_item["path"]] == [
        "Game systems",
        "Battle system",
    ]
    assert any(child["id"] == damage["id"] for child in battle_item["children"])


def test_agent_context_trail_requires_bearer_and_returns_markdown(
    enforce_auth_client, agent_headers
):
    project_id = _new_project(enforce_auth_client, agent_headers)
    node = enforce_auth_client.post(
        f"/api/v1/projects/{project_id}/knowledge",
        json={
            "title": "Battle component",
            "node_type": "SUMMARY",
            "content": "The battle component renders turn order and damage preview.",
        },
        headers=agent_headers,
    ).json()

    url = f"/api/v1/agent/projects/{project_id}/context-trail"
    assert enforce_auth_client.get(url, params={"query": "battle"}).status_code == 401

    response = enforce_auth_client.get(url, params={"query": "battle"}, headers=agent_headers)
    assert response.status_code == 200
    assert "Suggested load order" in response.text
    assert f"[SUMMARY #{node['id']}]" in response.text
