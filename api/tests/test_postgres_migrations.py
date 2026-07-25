"""PostgreSQL-only migration regressions that SQLite cannot represent."""

from __future__ import annotations

import asyncio
import base64
import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlmodel import Session, select

from api.migrations.runtime import (
    assert_database_current,
    assert_schema_matches_metadata,
    upgrade_database,
)
from api.backup import (
    create_backup,
    reset_restore_drill_target,
    restore_backup,
)
from api.config import get_settings
from api.events import Event, EventBroadcaster
from api.models.entities import (
    AuditLog,
    Project,
    Subproject,
    Ticket,
    User,
    Workspace,
    WorkspaceMembership,
)
from api.models.enums import (
    ActorRole,
    AuditAction,
    SSEAction,
    WorkspaceRole,
)
from api.routes.tickets import _claim_ticket_atomic
from api.utils.time import utcnow


@pytest.fixture
def postgres_engine():
    raw_url = os.environ.get("POSTGRES_TEST_URL")
    if not raw_url:
        pytest.skip("POSTGRES_TEST_URL is not configured")
    parsed = make_url(raw_url)
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.database != "taskable_test"
        or parsed.host not in {"localhost", "127.0.0.1"}
    ):
        pytest.fail(
            "PostgreSQL integration tests require the dedicated loopback "
            "database named taskable_test."
        )

    engine = create_engine(raw_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    try:
        yield engine
    finally:
        engine.dispose()


def test_legacy_audit_enum_is_repaired_before_claim_audit(
    postgres_engine,
) -> None:
    upgrade_database(
        postgres_engine,
        "0004_session_key_security",
    )

    # Reproduce the exact pre-Alembic production shape: the native enum lacks
    # the two coordination actions even though the table/revision is current.
    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE auditlog ALTER COLUMN action TYPE text "
                "USING action::text"
            )
        )
        connection.execute(text("DROP TYPE auditaction"))
        connection.execute(
            text(
                "CREATE TYPE auditaction AS ENUM "
                "('STATUS_UPDATE', 'CONTENT_UPDATE', 'MR_LINKED')"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE auditlog ALTER COLUMN action TYPE auditaction "
                "USING action::auditaction"
            )
        )

    with pytest.raises(RuntimeError, match="auditaction"):
        assert_schema_matches_metadata(postgres_engine)

    upgrade_database(postgres_engine, backup_confirmed=True)
    assert_database_current(postgres_engine)
    assert_schema_matches_metadata(postgres_engine)

    with postgres_engine.connect() as connection:
        labels = list(
            connection.execute(
                text(
                    "SELECT enumlabel FROM pg_enum "
                    "JOIN pg_type ON pg_type.oid = pg_enum.enumtypid "
                    "WHERE pg_type.typname = 'auditaction' "
                    "ORDER BY enumsortorder"
                )
            ).scalars()
        )
    assert labels == [
        "STATUS_UPDATE",
        "CONTENT_UPDATE",
        "MR_LINKED",
        "TICKET_CLAIMED",
        "TICKET_REQUEUED",
    ]

    with Session(postgres_engine) as session:
        project = Project(name="PostgreSQL claim")
        session.add(project)
        session.flush()
        subproject = Subproject(
            project_id=project.id,  # type: ignore[arg-type]
            name="Enum regression",
        )
        session.add(subproject)
        session.flush()
        ticket = Ticket(
            subproject_id=subproject.id,  # type: ignore[arg-type]
            title="Claim without a 500",
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)

        assert _claim_ticket_atomic(
            session,
            ticket.id,  # type: ignore[arg-type]
            "postgres-worker",
            utcnow(),
        )
        session.add(
            AuditLog(
                ticket_id=ticket.id,  # type: ignore[arg-type]
                action=AuditAction.TICKET_CLAIMED,
                actor=ActorRole.AGENT,
            )
        )
        session.add(
            AuditLog(
                ticket_id=ticket.id,  # type: ignore[arg-type]
                action=AuditAction.TICKET_REQUEUED,
                actor=ActorRole.AGENT,
            )
        )
        session.commit()

        session.refresh(ticket)
        assert ticket.claimed_by == "postgres-worker"
        assert ticket.status.value == "IN_PROGRESS"


def test_postgres_encrypted_backup_restores_into_fresh_database(
    postgres_engine,
    tmp_path,
    monkeypatch,
) -> None:
    raw_url = os.environ["POSTGRES_TEST_URL"]
    parsed = make_url(raw_url)
    restore_database = "mouvadah_restore_drill_test"
    restore_url = parsed.set(database=restore_database).render_as_string(
        hide_password=False
    )
    admin_url = parsed.set(database="postgres").render_as_string(
        hide_password=False
    )
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(
            text(
                "DROP DATABASE IF EXISTS mouvadah_restore_drill_test "
                "WITH (FORCE)"
            )
        )
        connection.execute(
            text("CREATE DATABASE mouvadah_restore_drill_test")
        )

    upgrade_database(postgres_engine)
    with Session(postgres_engine) as session:
        user = User(
            google_id="postgres-recovery-user",
            email="postgres-recovery@example.com",
            name="PostgreSQL Recovery",
        )
        workspace = Workspace(
            name="PostgreSQL recovery",
            slug="postgresql-recovery",
        )
        session.add_all([user, workspace])
        session.flush()
        session.add(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=user.id,
                role=WorkspaceRole.OWNER,
            )
        )
        session.add(
            Project(
                workspace_id=workspace.id,
                name="Restored PostgreSQL project",
            )
        )
        session.commit()

    backup_path = tmp_path / "postgres.mouvadah-backup"
    encryption_key = base64.b64encode(b"p" * 32).decode("ascii")
    host_override = os.environ.get("POSTGRES_TOOL_HOST_OVERRIDE")
    try:
        manifest = create_backup(
            raw_url,
            backup_path,
            encryption_key=encryption_key,
            postgres_host_override=host_override,
        )
        assert manifest["authenticated"]["archive_format"] == (
            "postgresql-custom"
        )

        restore_backup(
            backup_path,
            restore_url,
            confirm_database=restore_database,
            encryption_key=encryption_key,
            postgres_host_override=host_override,
        )
        restored_engine = create_engine(restore_url)
        try:
            assert_database_current(restored_engine)
            assert_schema_matches_metadata(restored_engine)
            with Session(restored_engine) as session:
                names = list(
                    session.exec(
                        select(Project.name).order_by(Project.id)
                    ).all()
                )
            assert names == ["Restored PostgreSQL project"]
        finally:
            restored_engine.dispose()

        monkeypatch.setenv("DATABASE_URL", raw_url)
        get_settings.cache_clear()
        reset_restore_drill_target(
            restore_url,
            confirm_database=restore_database,
        )
        scrubbed_engine = create_engine(restore_url)
        try:
            assert inspect(scrubbed_engine).get_table_names() == []
        finally:
            scrubbed_engine.dispose()
    finally:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "DROP DATABASE IF EXISTS mouvadah_restore_drill_test "
                    "WITH (FORCE)"
                )
            )
        admin_engine.dispose()


@pytest.mark.asyncio
async def test_postgres_realtime_fans_out_across_process_boundaries(
    postgres_engine,
) -> None:
    raw_url = os.environ["POSTGRES_TEST_URL"]
    first = EventBroadcaster()
    second = EventBroadcaster()
    event = Event(
        action=SSEAction.TICKET_UPDATED,
        entity="ticket",
        entity_id=73,
        parent_id=11,
        workspace_id=5,
    )
    await first.start(raw_url)
    await second.start(raw_url)
    try:
        async with second.subscribe() as queue:
            await first.publish(event)
            received = await asyncio.wait_for(queue.get(), timeout=3.0)
        assert received == event
        assert first.status() == "healthy"
        assert second.status() == "healthy"
    finally:
        await first.stop()
        await second.stop()
