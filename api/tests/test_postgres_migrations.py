"""PostgreSQL-only migration regressions that SQLite cannot represent."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session

from api.migrations.runtime import (
    assert_database_current,
    assert_schema_matches_metadata,
    upgrade_database,
)
from api.models.entities import AuditLog, Project, Subproject, Ticket
from api.models.enums import ActorRole, AuditAction
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
