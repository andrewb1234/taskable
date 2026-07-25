"""Seed the isolated Playwright database with one authenticated owner.

This script is intentionally locked to ``web/tests/.e2e-taskable.db``. It
refuses any other database URL before deleting or writing data so it cannot be
misused against a developer or hosted database.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import Session

from api.auth import hash_api_key
from api.database import engine
from api.migrations.runtime import upgrade_database
from api.models.entities import (
    ApiKey,
    User,
    Workspace,
    WorkspaceMembership,
)
from api.models.enums import WorkspaceRole

E2E_USER_ID = 1
E2E_WORKSPACE_ID = 1
E2E_EMAIL = "playwright@example.invalid"


def _validated_database_path() -> Path:
    configured = engine.url.database
    if not configured:
        raise RuntimeError("Playwright seeding requires a file-backed SQLite URL.")
    actual = Path(configured).resolve()
    expected = (
        Path(__file__).resolve().parents[1]
        / "web"
        / "tests"
        / ".e2e-taskable.db"
    ).resolve()
    if engine.dialect.name != "sqlite" or actual != expected:
        raise RuntimeError(
            "Refusing to seed outside web/tests/.e2e-taskable.db."
        )
    return actual


def main() -> None:
    raw_api_key = os.environ.get("E2E_API_KEY")
    if not raw_api_key:
        raise RuntimeError("E2E_API_KEY is required.")

    database_path = _validated_database_path()
    engine.dispose()
    for suffix in ("", "-shm", "-wal"):
        Path(f"{database_path}{suffix}").unlink(missing_ok=True)

    upgrade_database(engine)
    with Session(engine) as session:
        session.add(
            User(
                id=E2E_USER_ID,
                google_id="playwright-user",
                email=E2E_EMAIL,
                name="Playwright Owner",
            )
        )
        session.add(
            Workspace(
                id=E2E_WORKSPACE_ID,
                name="Playwright Workspace",
                slug="playwright-workspace",
            )
        )
        session.add(
            WorkspaceMembership(
                id=1,
                workspace_id=E2E_WORKSPACE_ID,
                user_id=E2E_USER_ID,
                role=WorkspaceRole.OWNER,
            )
        )
        session.add(
            ApiKey(
                id=1,
                user_id=E2E_USER_ID,
                workspace_id=E2E_WORKSPACE_ID,
                name="Playwright",
                key_prefix=raw_api_key[:12],
                key_hash=hash_api_key(raw_api_key),
                scopes=["read", "write"],
            )
        )
        session.commit()


if __name__ == "__main__":
    main()
