"""Centralized UTC timestamp helper.

Python 3.12+ deprecates ``datetime.utcnow``. The spec in ``docs/db_schema.md``
says defaults should be ``datetime.utcnow``; we honor the intent (naive UTC)
while using the non-deprecated call and keeping a single point of change.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return a timezone-naive UTC timestamp.

    Uses ``datetime.now(timezone.utc).replace(tzinfo=None)`` so the emitted
    value is comparable with existing SQLite DATETIME columns (which are
    stored as naive UTC ISO strings by SQLModel).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
