"""Authenticated local-owner provisioning and credential-file coverage."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from sqlmodel import select

from api.api_keys import hash_api_key
from api.local_setup import (
    LOCAL_KEY_NAME,
    provision_local_owner,
    read_credentials_file,
    write_credentials_file,
)
from api.models.entities import ApiKey, WorkspaceMembership
from api.models.enums import WorkspaceRole


def test_local_setup_creates_owner_workspace_and_reusable_key(session):
    first = provision_local_owner(
        session,
        email="Owner@Example.com",
        name="Local Owner",
    )

    assert first.user.google_id.startswith("local:")
    assert first.user.email == "owner@example.com"
    assert first.api_key.key_hash == hash_api_key(first.raw_key)
    membership = session.exec(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == first.user.id
        )
    ).one()
    assert membership.role == WorkspaceRole.OWNER

    second = provision_local_owner(
        session,
        email="owner@example.com",
        name="Renamed Owner",
        existing_key=first.raw_key,
    )

    assert second.reused_key is True
    assert second.user.id == first.user.id
    assert second.user.name == "Renamed Owner"
    assert second.api_key.id == first.api_key.id


def test_local_setup_rotation_revokes_prior_bootstrap_key(session):
    first = provision_local_owner(
        session,
        email="owner@example.com",
        name="Local Owner",
    )

    replacement = provision_local_owner(
        session,
        email="owner@example.com",
        name="Local Owner",
        existing_key=first.raw_key,
        rotate_key=True,
    )

    session.refresh(first.api_key)
    assert first.api_key.revoked is True
    assert replacement.api_key.id != first.api_key.id
    assert replacement.raw_key != first.raw_key
    active_bootstrap_keys = session.exec(
        select(ApiKey).where(
            ApiKey.user_id == first.user.id,
            ApiKey.name == LOCAL_KEY_NAME,
            ApiKey.revoked.is_(False),
        )
    ).all()
    assert [key.id for key in active_bootstrap_keys] == [
        replacement.api_key.id
    ]


def test_existing_credentials_must_belong_to_requested_owner(session):
    first = provision_local_owner(
        session,
        email="first@example.com",
        name="First Owner",
    )

    with pytest.raises(ValueError, match="active key"):
        provision_local_owner(
            session,
            email="second@example.com",
            name="Second Owner",
            existing_key=first.raw_key,
        )


def test_credentials_file_is_atomic_owner_only_and_round_trips(tmp_path):
    credentials_file = tmp_path / "config" / "credentials.env"

    write_credentials_file(credentials_file, "taskable_test-secret")

    assert read_credentials_file(credentials_file) == "taskable_test-secret"
    if os.name == "posix":
        assert stat.S_IMODE(credentials_file.stat().st_mode) == 0o600
        assert stat.S_IMODE(credentials_file.parent.stat().st_mode) == 0o700


def test_credentials_file_rejects_group_or_other_read_access(tmp_path):
    if os.name != "posix":
        pytest.skip("POSIX permission semantics required")
    credentials_file = tmp_path / "credentials.env"
    write_credentials_file(credentials_file, "taskable_test-secret")
    credentials_file.chmod(0o644)

    with pytest.raises(ValueError, match="readable by group/other"):
        read_credentials_file(credentials_file)


def test_local_setup_cli_is_fresh_install_safe_and_idempotent(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    database_path = tmp_path / "state" / "taskable.db"
    credentials_file = tmp_path / "config" / "credentials.env"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database_path}",
        "FRONTEND_URL": "http://localhost:5173",
        "LOCAL_AUTH_ENABLED": "true",
        "JWT_SECRET": "local-test-secret-at-least-32-bytes",
        "MIGRATION_MODE": "upgrade",
    }
    command = [
        sys.executable,
        "-m",
        "api.local_setup",
        "--email",
        "owner@example.com",
        "--name",
        "Local Owner",
        "--credentials-file",
        str(credentials_file),
    ]

    first = subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    second = subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "Created local owner" in first.stdout
    assert "Reused local owner" in second.stdout
    assert database_path.exists()
    assert read_credentials_file(credentials_file).startswith("taskable_")
