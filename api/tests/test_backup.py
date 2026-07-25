"""Authenticated encrypted backup and restore safety tests."""

from __future__ import annotations

import base64
import json

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, select

from api.backup import (
    BackupError,
    _safe_postgres_url,
    create_backup,
    reset_restore_drill_target,
    restore_backup,
    verify_backup,
)
from api.config import get_settings
from api.migrations.runtime import (
    assert_database_current,
    assert_schema_matches_metadata,
    upgrade_database,
)
from api.models.entities import (
    Project,
    User,
    Workspace,
    WorkspaceMembership,
)
from api.models.enums import WorkspaceRole


def _key(byte: bytes = b"k") -> str:
    return base64.b64encode(byte * 32).decode("ascii")


def _seed_database(path):
    database_url = f"sqlite:///{path}"
    engine = create_engine(database_url)
    upgrade_database(engine)
    with Session(engine) as session:
        user = User(
            google_id="backup-user",
            email="backup@example.com",
            name="Backup User",
        )
        workspace = Workspace(name="Backup workspace", slug="backup-workspace")
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
                name="Plaintext must remain encrypted",
            )
        )
        session.commit()
    engine.dispose()
    return database_url


def test_postgres_password_is_removed_from_command_url():
    safe_url, environment = _safe_postgres_url(
        "postgresql://backup-user:do-not-log-me@db.example.com/mouvadah"
    )

    assert "do-not-log-me" not in safe_url
    assert "backup-user@db.example.com/mouvadah" in safe_url
    assert environment["PGPASSWORD"] == "do-not-log-me"


def test_sqlite_backup_is_encrypted_verified_and_restorable(tmp_path):
    source_path = tmp_path / "source.db"
    source_url = _seed_database(source_path)
    backup_path = tmp_path / "daily.mouvadah-backup"

    manifest = create_backup(
        source_url,
        backup_path,
        encryption_key=_key(),
        key_id="recovery-2026-07",
    )

    assert backup_path.exists()
    assert backup_path.stat().st_mode & 0o777 == 0o600
    assert b"Plaintext must remain encrypted" not in backup_path.read_bytes()
    assert manifest["authenticated"]["archive_format"] == "sqlite"
    assert manifest["authenticated"]["key_id"] == "recovery-2026-07"
    assert verify_backup(backup_path, encryption_key=_key()) == manifest

    target_path = tmp_path / "restored.db"
    target_url = f"sqlite:///{target_path}"
    restored = restore_backup(
        backup_path,
        target_url,
        confirm_database=target_path.name,
        encryption_key=_key(),
    )
    assert restored == manifest

    engine = create_engine(target_url)
    assert_database_current(engine)
    assert_schema_matches_metadata(engine)
    with Session(engine) as session:
        project_names = list(
            session.exec(select(Project.name).order_by(Project.id)).all()
        )
    engine.dispose()
    assert project_names == ["Plaintext must remain encrypted"]


def test_wrong_key_and_modified_ciphertext_fail_closed(tmp_path):
    source_url = _seed_database(tmp_path / "source.db")
    backup_path = tmp_path / "daily.mouvadah-backup"
    create_backup(source_url, backup_path, encryption_key=_key())

    with pytest.raises(BackupError, match="authentication failed"):
        verify_backup(backup_path, encryption_key=_key(b"x"))

    manifest_path = backup_path.with_name(
        f"{backup_path.name}.manifest.json"
    )
    original_manifest = manifest_path.read_bytes()
    modified_manifest = json.loads(original_manifest)
    modified_manifest["authenticated"]["key_id"] = "attacker-modified"
    manifest_path.write_text(
        json.dumps(modified_manifest),
        encoding="utf-8",
    )
    with pytest.raises(BackupError, match="authentication failed"):
        verify_backup(backup_path, encryption_key=_key())
    manifest_path.write_bytes(original_manifest)

    content = bytearray(backup_path.read_bytes())
    content[len(content) // 2] ^= 1
    backup_path.write_bytes(content)
    with pytest.raises(BackupError, match="hash does not match"):
        verify_backup(backup_path, encryption_key=_key())


def test_restore_guards_confirmation_existing_targets_and_configured_db(
    tmp_path,
    monkeypatch,
):
    source_path = tmp_path / "source.db"
    source_url = _seed_database(source_path)
    backup_path = tmp_path / "daily.mouvadah-backup"
    create_backup(source_url, backup_path, encryption_key=_key())

    target_path = tmp_path / "target.db"
    with pytest.raises(BackupError, match="confirmation"):
        restore_backup(
            backup_path,
            f"sqlite:///{target_path}",
            confirm_database="wrong.db",
            encryption_key=_key(),
        )

    target_path.write_text("occupied", encoding="utf-8")
    with pytest.raises(BackupError, match="non-empty SQLite target"):
        restore_backup(
            backup_path,
            f"sqlite:///{target_path}",
            confirm_database=target_path.name,
            encryption_key=_key(),
        )

    monkeypatch.setenv("DATABASE_URL", source_url)
    get_settings.cache_clear()
    with pytest.raises(BackupError, match="configured application database"):
        restore_backup(
            backup_path,
            source_url,
            confirm_database=source_path.name,
            encryption_key=_key(),
        )


def test_restore_drill_reset_rejects_non_postgres_and_unsafe_names(
    monkeypatch,
):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///configured.db")
    get_settings.cache_clear()

    with pytest.raises(BackupError, match="PostgreSQL target"):
        reset_restore_drill_target(
            "sqlite:///mouvadah_restore_drill.db",
            confirm_database="mouvadah_restore_drill.db",
        )

    with pytest.raises(BackupError, match="must start"):
        reset_restore_drill_target(
            "postgresql://operator:secret@db.example.com/customer_data",
            confirm_database="customer_data",
        )


def test_restore_drill_reset_rejects_configured_application_database(
    monkeypatch,
):
    configured_url = (
        "postgresql://operator:secret@db.example.com/"
        "mouvadah_restore_drill_production"
    )
    monkeypatch.setenv("DATABASE_URL", configured_url)
    get_settings.cache_clear()

    with pytest.raises(
        BackupError,
        match="configured application database",
    ):
        reset_restore_drill_target(
            configured_url,
            confirm_database="mouvadah_restore_drill_production",
        )
