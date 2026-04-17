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

from api.events import get_broadcaster

router = APIRouter(tags=["events"])

_HEARTBEAT_SECONDS = 15.0


@router.get("/events")
async def stream_events(request: Request) -> EventSourceResponse:
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
                yield {"event": "message", "data": event.to_json()}

    return EventSourceResponse(event_generator())
