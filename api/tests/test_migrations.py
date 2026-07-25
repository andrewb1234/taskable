"""Alembic bootstrap, adoption, backup, and schema-parity coverage."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session, SQLModel

import api.models.entities  # noqa: F401
from api.migrations.runtime import (
    BASELINE_REVISION,
    MigrationSafetyError,
    UnsupportedSchemaError,
    _prepare_backup,
    assert_database_current,
    assert_schema_matches_metadata,
    current_revision,
    head_revision,
    schema_diffs,
    upgrade_database,
)
from api.models.entities import Project


def _sqlite_engine(path: Path):
    return create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )


def test_fresh_database_upgrades_to_head_and_is_idempotent(tmp_path):
    engine = _sqlite_engine(tmp_path / "fresh.db")

    first = upgrade_database(engine)
    second = upgrade_database(engine)

    assert first.adopted_state == "empty"
    assert first.backup_path is None
    assert first.current_revision == head_revision()
    assert second.previous_revision == head_revision()
    assert second.backup_path is None
    assert current_revision(engine) == head_revision()
    assert schema_diffs(engine) == []
    assert_database_current(engine)
    assert_schema_matches_metadata(engine)


def test_unversioned_pre_tenancy_database_is_backed_up_and_preserved(
    tmp_path,
):
    database_path = tmp_path / "legacy.db"
    engine = _sqlite_engine(database_path)
    upgrade_database(engine, BASELINE_REVISION)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO project "
                "(id, name, description, created_at) "
                "VALUES (101, 'Legacy project', 'Keep me', "
                "'2026-07-25 00:00:00')"
            )
        )
        connection.execute(text("DROP TABLE alembic_version"))

    result = upgrade_database(engine)

    assert result.adopted_state == "pre_tenancy"
    assert result.current_revision == head_revision()
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert result.backup_path.parent == database_path.parent
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT name, description, workspace_id "
                "FROM project WHERE id = 101"
            )
        ).one()
    assert tuple(row) == ("Legacy project", "Keep me", None)
    backup_engine = _sqlite_engine(result.backup_path)
    assert "workspace_id" not in {
        column["name"]
        for column in inspect(backup_engine).get_columns("project")
    }
    assert schema_diffs(engine) == []


def test_unversioned_head_schema_is_stamped_without_data_loss(tmp_path):
    engine = _sqlite_engine(tmp_path / "unversioned-head.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        project = Project(name="Already migrated")
        session.add(project)
        session.commit()
        project_id = project.id

    result = upgrade_database(engine)

    assert result.adopted_state == "head"
    assert result.current_revision == head_revision()
    assert result.backup_path is not None
    with Session(engine) as session:
        preserved = session.get(Project, project_id)
        assert preserved is not None
        assert preserved.name == "Already migrated"
    assert schema_diffs(engine) == []


def test_partial_unversioned_schema_fails_closed(tmp_path):
    engine = _sqlite_engine(tmp_path / "partial.db")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE project ("
                "id INTEGER PRIMARY KEY, name VARCHAR NOT NULL"
                ")"
            )
        )

    with pytest.raises(
        UnsupportedSchemaError,
        match="does not match the supported 0.1.0",
    ):
        upgrade_database(engine)

    assert "alembic_version" not in inspect(engine).get_table_names()


def test_check_mode_rejects_unversioned_database(tmp_path):
    engine = _sqlite_engine(tmp_path / "check.db")
    SQLModel.metadata.create_all(engine)

    with pytest.raises(RuntimeError, match="unversioned"):
        assert_database_current(engine)


def test_existing_non_sqlite_database_requires_backup_confirmation():
    fake_engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
    )

    with pytest.raises(MigrationSafetyError, match="backup confirmation"):
        _prepare_backup(
            fake_engine,
            has_application_data=True,
            backup_confirmed=False,
        )
    assert (
        _prepare_backup(
            fake_engine,
            has_application_data=True,
            backup_confirmed=True,
        )
        is None
    )


def test_api_key_migration_backfills_only_unambiguous_workspace_ownership(
    tmp_path,
):
    engine = _sqlite_engine(tmp_path / "api-key-scope.db")
    upgrade_database(engine, "0003_dependency_unique")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO user "
                "(id, google_id, email, name, created_at) VALUES "
                "(1, 'g-1', 'one@example.com', 'One', '2026-07-25'), "
                "(2, 'g-2', 'two@example.com', 'Two', '2026-07-25')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO workspace (id, name, slug, created_at) VALUES "
                "(10, 'One', 'one', '2026-07-25'), "
                "(20, 'Two A', 'two-a', '2026-07-25'), "
                "(21, 'Two B', 'two-b', '2026-07-25')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO workspacemembership "
                "(workspace_id, user_id, role, created_at) VALUES "
                "(10, 1, 'OWNER', '2026-07-25'), "
                "(20, 2, 'OWNER', '2026-07-25'), "
                "(21, 2, 'MEMBER', '2026-07-25')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO apikey "
                "(id, user_id, name, key_prefix, key_hash, revoked, created_at) "
                "VALUES "
                "(100, 1, 'one', 'one', 'hash-one', 0, '2026-07-25'), "
                "(200, 2, 'two', 'two', 'hash-two', 0, '2026-07-25')"
            )
        )

    result = upgrade_database(engine)

    assert result.current_revision == head_revision()
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, workspace_id, scopes, revoked "
                "FROM apikey ORDER BY id"
            )
        ).all()
    assert rows[0].id == 100
    assert rows[0].workspace_id == 10
    assert "read" in rows[0].scopes and "write" in rows[0].scopes
    assert rows[0].revoked == 0
    assert rows[1].id == 200
    assert rows[1].workspace_id is None
    assert rows[1].revoked == 1
    assert {"browsersession", "apikeyproject"}.issubset(
        inspect(engine).get_table_names()
    )
    assert schema_diffs(engine) == []
