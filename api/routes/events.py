"""Server-Sent Events stream.

Every connected UI client holds an open GET /events connection; the
``EventBroadcaster`` singleton fans out state-change notifications so the
Kanban board can re-fetch the affected entity in the background.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from sqlmodel import select

from api.auth import CurrentUser
from api.dependencies import SessionDep
from api.events import get_broadcaster
from api.models.entities import WorkspaceMembership

router = APIRouter(tags=["events"])

_HEARTBEAT_SECONDS = 15.0


def can_receive_event(session, user, event) -> bool:
    """Return whether a caller currently belongs to an event's workspace."""
    if event.workspace_id is None:
        return False
    return (
        session.exec(
            select(WorkspaceMembership.id).where(
                WorkspaceMembership.workspace_id == event.workspace_id,
                WorkspaceMembership.user_id == user.id,
            )
        ).first()
        is not None
    )


@router.get("/events")
async def stream_events(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> EventSourceResponse:
    """Stream SSE events. Emits a heartbeat comment every 15s to keep the
    connection alive through proxies/load-balancers."""

    broadcaster = get_broadcaster()

    async def event_generator() -> AsyncIterator[dict]:
        async with broadcaster.subscribe() as queue:
            # Prime the stream so the client knows we're live.
            yield {"event": "ready", "data": "ok"}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    # SSE "comment" line → keeps the connection warm.
                    yield {"comment": "heartbeat"}
                    continue
                # Re-check membership for every event so a revoked user does
                # not retain realtime access through an already-open stream.
                if not can_receive_event(session, user, event):
                    continue
                yield {"event": "message", "data": event.to_json()}

    return EventSourceResponse(event_generator())
