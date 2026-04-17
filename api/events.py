"""In-process SSE broadcaster.

Any route that mutates state pushes an event here; the ``/events`` SSE stream
forwards it to every connected UI client.

We use a dedicated ``asyncio.Queue`` per subscriber and a single global
``EventBroadcaster`` singleton. This is deliberately simple (no Redis, no
multi-process fan-out) because ``prd.md`` targets a local-first workspace.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

from api.models.enums import SSEAction


@dataclass(frozen=True)
class Event:
    """Payload broadcast over the SSE stream."""

    action: SSEAction
    entity: str
    entity_id: int
    parent_id: int | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "action": self.action.value,
                "entity": self.entity,
                "entity_id": self.entity_id,
                "parent_id": self.parent_id,
            }
        )


@dataclass
class EventBroadcaster:
    """Fan-out async broadcaster with per-subscriber backpressure."""

    _subscribers: set[asyncio.Queue[Event]] = field(default_factory=set)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _queue_maxsize: int = 128

    async def publish(self, event: Event) -> None:
        """Non-blocking publish. Drops events for slow subscribers."""
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Fail-soft: slow clients lose deltas but stay connected.
                continue

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[Event]]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_maxsize)
        async with self._lock:
            self._subscribers.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    # -- test helpers -----------------------------------------------------

    def subscriber_count(self) -> int:
        return len(self._subscribers)


_broadcaster: EventBroadcaster | None = None


def get_broadcaster() -> EventBroadcaster:
    """Return the singleton broadcaster, constructing on first use."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster


def reset_broadcaster() -> None:  # pragma: no cover - test-only helper
    """Force-create a fresh broadcaster. Used by pytest fixtures."""
    global _broadcaster
    _broadcaster = EventBroadcaster()
