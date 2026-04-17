"""SQLite engine + session dependency.

Uses SQLModel's ``create_engine`` with the ``check_same_thread=False`` flag so
FastAPI's thread pool can share a single connection pool. The database file
lives alongside the API code under ``./data/`` by default and is created on
startup via ``init_db``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from api.config import get_settings


def _engine_kwargs(url: str) -> dict:
    kwargs: dict = {"echo": False}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


def _ensure_sqlite_dir(url: str) -> None:
    """Create the directory hosting the SQLite file if missing."""
    if not url.startswith("sqlite"):
        return
    # Forms: sqlite:///./data/foo.db, sqlite:////abs/path/foo.db, sqlite:///:memory:
    path_part = url.split("sqlite:///", 1)[-1]
    if path_part in {"", ":memory:"}:
        return
    db_path = Path(path_part)
    db_path.parent.mkdir(parents=True, exist_ok=True)


_settings = get_settings()
_ensure_sqlite_dir(_settings.database_url)
engine = create_engine(_settings.database_url, **_engine_kwargs(_settings.database_url))


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    # Importing models ensures they are registered with SQLModel.metadata.
    import api.models.entities  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a short-lived Session."""
    with Session(engine) as session:
        yield session


# Override hook used by the pytest conftest to swap in an in-memory engine.
def _set_engine(new_engine) -> None:  # pragma: no cover - test-only helper
    global engine
    engine = new_engine


__all__ = ["engine", "init_db", "get_session", "_set_engine"]
