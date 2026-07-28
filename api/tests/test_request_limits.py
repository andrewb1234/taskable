"""Bound authenticated input before it becomes a storage or memory attack."""

from __future__ import annotations

from api.schemas import (
    MAX_COMMENT_LENGTH,
    MAX_DEPENDENCIES,
    MAX_LONG_TEXT_LENGTH,
    MAX_REFERENCES,
)


def test_request_body_limit_rejects_before_route_parsing(client) -> None:
    response = client.post(
        "/api/v1/projects",
        content=b"x" * 1_048_577,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert "1048576-byte limit" in response.json()["detail"]


def test_long_text_and_collection_limits_are_enforced(client) -> None:
    too_long_project = client.post(
        "/api/v1/projects",
        json={
            "name": "bounded",
            "description": "x" * (MAX_LONG_TEXT_LENGTH + 1),
        },
    )
    project = client.post(
        "/api/v1/projects",
        json={"name": "valid"},
    ).json()
    too_many_references = client.post(
        f"/api/v1/projects/{project['id']}/knowledge",
        json={
            "title": "bounded",
            "source_refs": [
                f"https://example.invalid/{index}"
                for index in range(MAX_REFERENCES + 1)
            ],
        },
    )
    subproject = client.post(
        f"/api/v1/projects/{project['id']}/subprojects",
        json={"name": "bounded"},
    ).json()
    too_many_dependencies = client.post(
        f"/api/v1/subprojects/{subproject['id']}/tickets",
        json={
            "title": "bounded",
            "depends_on": list(range(MAX_DEPENDENCIES + 1)),
        },
    )

    assert too_long_project.status_code == 422
    assert too_many_references.status_code == 422
    assert too_many_dependencies.status_code == 422


def test_comment_and_link_protocol_limits_are_enforced(client) -> None:
    project = client.post(
        "/api/v1/projects",
        json={"name": "valid"},
    ).json()
    subproject = client.post(
        f"/api/v1/projects/{project['id']}/subprojects",
        json={"name": "valid"},
    ).json()
    ticket = client.post(
        f"/api/v1/subprojects/{subproject['id']}/tickets",
        json={"title": "valid"},
    ).json()

    long_comment = client.post(
        f"/api/v1/tickets/{ticket['id']}/comments",
        json={
            "author": "HUMAN",
            "content": "x" * (MAX_COMMENT_LENGTH + 1),
        },
    )
    unsafe_link = client.post(
        f"/api/v1/tickets/{ticket['id']}/mr",
        json={"url": "javascript:alert(1)"},
    )

    assert long_comment.status_code == 422
    assert unsafe_link.status_code == 422
