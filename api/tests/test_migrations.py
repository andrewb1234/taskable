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
