"""Pytest harness.

Swaps the production engine for a fresh in-memory SQLite per test so state
is completely isolated, and resets the SSE broadcaster so event-publishing
tests don't leak queues across runs.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from api import database, events
from api.dependencies import get_session
from api.main import app

TEST_AGENT_API_KEY = "test-agent-key"


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch) -> None:
    """Pin config to deterministic values for every test."""
    monkeypatch.setenv("AGENT_API_KEY", TEST_AGENT_API_KEY)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    # Reset cached settings so the new env wins.
    from api.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def engine():
    """In-memory SQLite shared across connections via StaticPool."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Register models and create schema.
    import api.models.entities  # noqa: F401

    SQLModel.metadata.create_all(test_engine)
    original_engine = database.engine
    database._set_engine(test_engine)
    try:
        yield test_engine
    finally:
        SQLModel.metadata.drop_all(test_engine)
        database._set_engine(original_engine)


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with Session(engine) as sess:
        yield sess


@pytest.fixture
def client(engine) -> Iterator[TestClient]:
    """FastAPI TestClient with the in-memory engine wired in."""

    def override_get_session() -> Iterator[Session]:
        with Session(engine) as sess:
            yield sess

    app.dependency_overrides[get_session] = override_get_session
    events.reset_broadcaster()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def agent_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_AGENT_API_KEY}"}
