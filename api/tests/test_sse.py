"""SSE broadcaster — intercept internal events during state mutations."""

from __future__ import annotations

import asyncio

import pytest

from api.events import Event, get_broadcaster, reset_broadcaster
from api.models.enums import SSEAction


@pytest.mark.asyncio
async def test_broadcaster_delivers_to_subscriber():
    reset_broadcaster()
    broadcaster = get_broadcaster()

    received: list[Event] = []

    async def listener():
        async with broadcaster.subscribe() as queue:
            received.append(await asyncio.wait_for(queue.get(), timeout=1.0))

    listener_task = asyncio.create_task(listener())
    await asyncio.sleep(0)  # let listener register
    await broadcaster.publish(
        Event(action=SSEAction.TICKET_UPDATED, entity="ticket", entity_id=1)
    )
    await listener_task

    assert received[0].action is SSEAction.TICKET_UPDATED
    assert received[0].entity_id == 1


def test_ticket_mutation_publishes_event(client, session):
    """State mutations must push an SSEAction.TICKET_UPDATED event."""
    captured: list[Event] = []
    broadcaster = get_broadcaster()
    original_publish = broadcaster.publish

    async def capturing_publish(event: Event) -> None:
        captured.append(event)
        await original_publish(event)

    broadcaster.publish = capturing_publish  # type: ignore[assignment]
    try:
        project = client.post("/api/v1/projects", json={"name": "P"}).json()
        sp = client.post(
            f"/api/v1/projects/{project['id']}/subprojects",
            json={"name": "S"},
        ).json()
        ticket = client.post(
            f"/api/v1/subprojects/{sp['id']}/tickets", json={"title": "T"}
        ).json()
        client.patch(
            f"/api/v1/tickets/{ticket['id']}", json={"status": "IN_PROGRESS"}
        )
    finally:
        broadcaster.publish = original_publish  # type: ignore[assignment]

    actions = [e.action for e in captured]
    assert SSEAction.PROJECT_CREATED in actions
    assert SSEAction.SUBPROJECT_CREATED in actions
    assert SSEAction.TICKET_CREATED in actions
    assert SSEAction.TICKET_UPDATED in actions
