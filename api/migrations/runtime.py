"""Safe Alembic execution for fresh and recognized legacy databases."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script.revision import ResolutionError
from alembic.script import ScriptDirectory
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine
from sqlmodel import SQLModel

BASELINE_REVISION = "0001_pre_tenancy"
TENANCY_REVISION = "0002_workspace_tenancy"

_API_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _API_DIR / "alembic.ini"
_SCRIPT_LOCATION = _API_DIR / "migrations"

_BASELINE_COLUMNS: dict[str, set[str]] = {
    "project": {"id", "name", "description", "created_at"},
    "subproject": {
        "id",
        "project_id",
        "name",
        "context_brief",
        "status",
    },
    "ticket": {
        "id",
        "subproject_id",
        "title",
        "description",
        "status",
        "assignee",
        "mr_link",
        "blocked_by",
        "blocked_reason",
        "source_refs",
        "claimed_by",
        "claimed_at",
        "lease_expires_at",
    },
    "ticketdependency": {"ticket_id", "depends_on_ticket_id"},
    "comment": {"id", "ticket_id", "author", "content", "timestamp"},
    "auditlog": {"id", "ticket_id", "action", "actor", "timestamp"},
    "knowledgenode": {
        "id",
        "project_id",
        "parent_id",
        "title",
        "node_type",
        "status",
        "superseded_by",
        "content",
        "source_refs",
        "created_by",
        "created_at",
        "updated_at",
    },
    "knowledgeproposal": {
        "id",
        "node_id",
        "proposed_by",
        "proposed_changes",
        "rationale",
        "status",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    },
    "agentsession": {
        "id",
        "project_id",
        "intent",
        "loaded_node_ids",
        "started_at",
        "ended_at",
        "handoff_note",
        "status",
    },
    "user": {
        "id",
        "google_id",
        "email",
        "name",
        "avatar_url",
        "created_at",
    },
    "apikey": {
        "id",
        "user_id",
        "name",
        "key_prefix",
        "key_hash",
        "expires_at",
        "last_used_at",
        "revoked",
        "created_at",
    },
}
_TENANCY_COLUMNS: dict[str, set[str]] = {
    **_BASELINE_COLUMNS,
    "project": _BASELINE_COLUMNS["project"] | {"workspace_id"},
    "workspace": {"id", "name", "slug", "created_at"},
    "workspacemembership": {
        "id",
        "workspace_id",
        "user_id",
        "role",
        "created_at",
    },
}
_HEAD_COLUMNS: dict[str, set[str]] = {
    **_TENANCY_COLUMNS,
    "apikey": _TENANCY_COLUMNS["apikey"] | {"workspace_id", "scopes"},
    "apikeyproject": {"api_key_id", "project_id"},
    "browsersession": {
        "id",
        "user_id",
        "expires_at",
        "revoked_at",
        "created_at",
        "last_seen_at",
    },
}
_KNOWN_APPLICATION_TABLES = set(_HEAD_COLUMNS)

SchemaState = Literal["empty", "pre_tenancy", "tenancy", "head"]


class UnsupportedSchemaError(RuntimeError):
    """Raised when an unversioned database cannot be adopted unambiguously."""


class MigrationSafetyError(RuntimeError):
    """Raised when a migration lacks the required backup evidence."""


@dataclass(frozen=True)
class MigrationResult:
    previous_revision: str | None
    current_revision: str
    adopted_state: SchemaState | None
    backup_path: Path | None


def alembic_config(connection: Connection | None = None) -> Config:
    """Build an Alembic config without putting database credentials in it."""
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option(
        "script_location",
        str(_SCRIPT_LOCATION).replace("%", "%%"),
    )
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(alembic_config())


def head_revision() -> str:
    heads = _script_directory().get_heads()
    if len(heads) != 1:
        raise RuntimeError(
            f"Expected one Alembic head, found {len(heads)}: {heads}"
        )
    return heads[0]


def current_revision(target_engine: Engine) -> str | None:
    with target_engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _missing_schema_parts(
    connection: Connection,
    required: dict[str, set[str]],
) -> list[str]:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    missing: list[str] = []
    for table, required_columns in required.items():
        if table not in tables:
            missing.append(f"table:{table}")
            continue
        actual_columns = {
            column["name"] for column in inspector.get_columns(table)
        }
        missing.extend(
            f"column:{table}.{column}"
            for column in sorted(required_columns - actual_columns)
        )
    return missing


def classify_unversioned_schema(connection: Connection) -> SchemaState:
    """Recognize only schemas that can be adopted without guessing."""
    inspector = inspect(connection)
    tables = set(inspector.get_table_names()) - {"alembic_version"}
    if not tables:
        return "empty"

    application_tables = tables & _KNOWN_APPLICATION_TABLES
    if not application_tables:
        raise UnsupportedSchemaError(
            "Database contains tables but no recognizable Mouvadah schema. "
            "Use a dedicated database or restore a verified backup."
        )

    workspace_markers = {
        "workspace",
        "workspacemembership",
    } & tables
    project_columns = (
        {
            column["name"]
            for column in inspector.get_columns("project")
        }
        if "project" in tables
        else set()
    )
    has_workspace_column = "workspace_id" in project_columns

    if workspace_markers or has_workspace_column:
        head_missing = _missing_schema_parts(connection, _HEAD_COLUMNS)
        if not head_missing:
            return "head"
        tenancy_missing = _missing_schema_parts(
            connection,
            _TENANCY_COLUMNS,
        )
        if not tenancy_missing:
            return "tenancy"
        raise UnsupportedSchemaError(
            "Database has a partial workspace migration and will not be "
            "modified automatically. Missing: " + ", ".join(tenancy_missing)
        )

    missing = _missing_schema_parts(connection, _BASELINE_COLUMNS)
    if missing:
        raise UnsupportedSchemaError(
            "Unversioned database does not match the supported 0.1.0 "
            "pre-tenancy baseline. Missing: " + ", ".join(missing)
        )
    return "pre_tenancy"


def _sqlite_backup(target_engine: Engine) -> Path | None:
    database = target_engine.url.database
    if not database or database == ":memory:":
        return None
    source_path = Path(database).expanduser().resolve()
    if not source_path.exists() or source_path.stat().st_size == 0:
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = source_path.with_name(
        f"{source_path.name}.pre-migration-{timestamp}.bak"
    )
    with (
        sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source,
        sqlite3.connect(backup_path) as destination,
    ):
        source.backup(destination)
    return backup_path


def _prepare_backup(
    target_engine: Engine,
    *,
    has_application_data: bool,
    backup_confirmed: bool,
) -> Path | None:
    if not has_application_data:
        return None
    if target_engine.dialect.name == "sqlite":
        return _sqlite_backup(target_engine)
    if not backup_confirmed:
        raise MigrationSafetyError(
            "Refusing to migrate an existing non-SQLite database without "
            "backup confirmation. Create and verify a database backup, then "
            "run `python -m api.migrations upgrade --backup-confirmed`."
        )
    return None


def upgrade_database(
    target_engine: Engine,
    revision: str = "head",
    *,
    backup_confirmed: bool = False,
) -> MigrationResult:
    """Adopt a recognized unversioned schema and migrate to ``revision``."""
    script = _script_directory()
    resolved_target = (
        head_revision()
        if revision == "head"
        else script.get_revision(revision).revision
    )

    with target_engine.connect() as connection:
        previous_revision = MigrationContext.configure(
            connection
        ).get_current_revision()
        tables = set(inspect(connection).get_table_names())
        adopted_state: SchemaState | None = None
        if previous_revision is None:
            adopted_state = classify_unversioned_schema(connection)

    if previous_revision == resolved_target:
        return MigrationResult(
            previous_revision=previous_revision,
            current_revision=resolved_target,
            adopted_state=None,
            backup_path=None,
        )

    if previous_revision is not None:
        try:
            script.get_revision(previous_revision)
        except ResolutionError as exc:
            raise UnsupportedSchemaError(
                f"Database references unknown Alembic revision "
                f"{previous_revision!r}."
            ) from exc

    if adopted_state == "head" and resolved_target != head_revision():
        raise UnsupportedSchemaError(
            "An unversioned head schema cannot be adopted at an older "
            f"revision ({resolved_target})."
        )

    backup_path = _prepare_backup(
        target_engine,
        has_application_data=bool(
            (tables - {"alembic_version"}) & _KNOWN_APPLICATION_TABLES
        ),
        backup_confirmed=backup_confirmed,
    )

    with target_engine.begin() as connection:
        config = alembic_config(connection)
        if adopted_state == "pre_tenancy":
            command.stamp(config, BASELINE_REVISION)
        elif adopted_state == "tenancy":
            # Unversioned tenancy databases may still carry compatibility
            # artifacts normalized by later revisions.
            command.stamp(config, TENANCY_REVISION)
        elif adopted_state == "head":
            command.stamp(config, head_revision())

        command.upgrade(config, resolved_target)

    migrated_revision = current_revision(target_engine)
    if migrated_revision != resolved_target:
        raise RuntimeError(
            "Migration completed without reaching the requested revision: "
            f"expected {resolved_target}, found {migrated_revision}."
        )
    return MigrationResult(
        previous_revision=previous_revision,
        current_revision=migrated_revision,
        adopted_state=adopted_state,
        backup_path=backup_path,
    )


def assert_database_current(target_engine: Engine) -> None:
    expected = head_revision()
    actual = current_revision(target_engine)
    if actual != expected:
        raise RuntimeError(
            "Database schema is not at the application migration head. "
            f"Expected {expected}, found {actual or 'unversioned'}. Run the "
            "single deployment migration job before starting the app."
        )


def schema_diffs(target_engine: Engine) -> list:
    """Return autogenerate differences between the database and ORM metadata."""
    import api.models.entities  # noqa: F401

    with target_engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "compare_type": True,
                "compare_server_default": False,
                "render_as_batch": True,
            },
        )
        diffs = list(compare_metadata(context, SQLModel.metadata))
        if connection.dialect.name == "postgresql":
            expected_enums: dict[str, tuple[str, ...]] = {}
            for table in SQLModel.metadata.tables.values():
                for column in table.columns:
                    if (
                        isinstance(column.type, SQLAlchemyEnum)
                        and column.type.name
                    ):
                        expected_enums[column.type.name] = tuple(
                            column.type.enums
                        )
            actual_enums = {
                enum["name"]: tuple(enum["labels"])
                for enum in inspect(connection).get_enums()
            }
            for name, expected_labels in sorted(expected_enums.items()):
                actual_labels = actual_enums.get(name)
                if actual_labels != expected_labels:
                    diffs.append(
                        (
                            "modify_postgresql_enum",
                            name,
                            actual_labels,
                            expected_labels,
                        )
                    )
        return diffs


def assert_schema_matches_metadata(target_engine: Engine) -> None:
    diffs = schema_diffs(target_engine)
    if diffs:
        raise RuntimeError(
            "Database is at migration head but differs from ORM metadata: "
            f"{diffs}"
        )
