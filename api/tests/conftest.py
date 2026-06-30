"""Pytest harness.

Swaps the production engine for a fresh in-memory SQLite per test so state
is completely isolated, and resets the SSE broadcaster so event-publishing
tests don't leak queues across runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from api import database, events
from api.auth import get_current_user, hash_api_key
from api.dependencies import get_session
from api.main import app
from api.models.entities import ApiKey, User

TEST_AGENT_API_KEY = "test-agent-key"


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch) -> None:
    """Pin config to deterministic values for every test."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
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
def test_user(engine) -> User:
    """Create a deterministic test user for auth overrides."""
    with Session(engine) as sess:
        user = User(
            google_id="test-google-id",
            email="test@example.com",
            name="Test User",
            avatar_url=None,
        )
        sess.add(user)
        sess.commit()
        sess.refresh(user)
        return user


@pytest.fixture
def client(engine, test_user) -> Iterator[TestClient]:
    """FastAPI TestClient with the in-memory engine and auth bypass wired in."""

    def override_get_session() -> Iterator[Session]:
        with Session(engine) as sess:
            yield sess

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    api_v1 = getattr(app, "api_v1", None)
    if api_v1 is not None:
        api_v1.dependency_overrides[get_session] = override_get_session
        api_v1.dependency_overrides[get_current_user] = override_get_current_user
    events.reset_broadcaster()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    if api_v1 is not None:
        api_v1.dependency_overrides.pop(get_session, None)
        api_v1.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def agent_headers(engine, test_user) -> dict[str, str]:
    """Create a real API key in the DB and return bearer headers for it."""
    with Session(engine) as sess:
        api_key = ApiKey(
            user_id=test_user.id,
            name="test-key",
            key_prefix=TEST_AGENT_API_KEY[:12],
            key_hash=hash_api_key(TEST_AGENT_API_KEY),
        )
        sess.add(api_key)
        sess.commit()
    return {"Authorization": f"Bearer {TEST_AGENT_API_KEY}"}


@pytest.fixture
def enforce_auth_client(engine, test_user) -> Iterator[TestClient]:
    """TestClient that does NOT bypass auth — real API key verification is exercised."""

    def override_get_session() -> Iterator[Session]:
        with Session(engine) as sess:
            yield sess

    app.dependency_overrides[get_session] = override_get_session
    api_v1 = getattr(app, "api_v1", None)
    if api_v1 is not None:
        api_v1.dependency_overrides[get_session] = override_get_session
    events.reset_broadcaster()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_session, None)
    if api_v1 is not None:
        api_v1.dependency_overrides.pop(get_session, None)
