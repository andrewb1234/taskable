"""Scheduled backup freshness and restore-drill runner regressions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _status(created_at: datetime) -> dict[str, object]:
    return {
        "backup_id": "backup-id",
        "ciphertext_sha256": "a" * 64,
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
        "key_id": "primary",
        "migration_revision": "0006_workspace_data_lifecycle",
        "object_etag": '"etag"',
        "object_key": (
            "mouvadah/database/20260725T030000Z.mouvadah-backup"
        ),
        "status": "verified",
    }


def _base_environment(fake_bin: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "AWS_ACCESS_KEY_ID": "test-access",
            "AWS_REGION": "us-west-2",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "BACKUP_ENCRYPTION_KEY": "not-used-by-fake-python",
            "BACKUP_S3_BUCKET": "backup-bucket",
            "DATABASE_URL": "postgresql://source/source",
            "PATH": (
                f"{fake_bin}{os.pathsep}{Path(sys.executable).parent}"
                f"{os.pathsep}{environment['PATH']}"
            ),
            "RESTORE_DRILL_CONFIRM_DATABASE": (
                "mouvadah_restore_drill_test"
            ),
            "RESTORE_DRILL_DATABASE_URL": (
                "postgresql://drill/drill"
            ),
        }
    )
    return environment


def test_backup_freshness_checker_accepts_recent_verified_marker(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    status_file = tmp_path / "status.json"
    status_file.write_text(
        json.dumps(_status(datetime.now(UTC))),
        encoding="utf-8",
    )
    _write_executable(
        fake_bin / "aws",
        """#!/bin/sh
set -eu
if [ "$1" = "s3" ] && [ "$2" = "cp" ]; then
  cp "$FAKE_STATUS_FILE" "$4"
  exit 0
fi
if [ "$1" = "s3api" ] && [ "$2" = "head-object" ]; then
  exit 0
fi
exit 64
""",
    )
    environment = _base_environment(fake_bin)
    environment["FAKE_STATUS_FILE"] = str(status_file)

    result = subprocess.run(
        ["sh", "scripts/check_backup_freshness.sh"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "both objects are present" in result.stdout


def test_backup_freshness_checker_fails_for_stale_marker(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    status_file = tmp_path / "status.json"
    status_file.write_text(
        json.dumps(_status(datetime.now(UTC) - timedelta(days=3))),
        encoding="utf-8",
    )
    _write_executable(
        fake_bin / "aws",
        """#!/bin/sh
set -eu
cp "$FAKE_STATUS_FILE" "$4"
""",
    )
    environment = _base_environment(fake_bin)
    environment["FAKE_STATUS_FILE"] = str(status_file)

    result = subprocess.run(
        ["sh", "scripts/check_backup_freshness.sh"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "latest verified backup is stale" in result.stderr


def test_restore_drill_runner_scrubs_target_and_uploads_evidence(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    status_file = tmp_path / "status.json"
    status_file.write_text(
        json.dumps(_status(datetime.now(UTC))),
        encoding="utf-8",
    )
    command_log = tmp_path / "python-commands.log"
    upload_log = tmp_path / "uploads.log"
    _write_executable(
        fake_bin / "python3",
        f"""#!/bin/sh
set -eu
if [ "$1" = "-m" ]; then
  printf '%s\\n' "$*" >> "$FAKE_COMMAND_LOG"
  exit 0
fi
exec {sys.executable} "$@"
""",
    )
    _write_executable(
        fake_bin / "aws",
        """#!/bin/sh
set -eu
if [ "$1" != "s3" ] || [ "$2" != "cp" ]; then
  exit 64
fi
case "$3" in
  s3://*/status/latest.json)
    cp "$FAKE_STATUS_FILE" "$4"
    ;;
  s3://*/*.manifest.json)
    printf '{}\\n' > "$4"
    ;;
  s3://*/*.mouvadah-backup)
    printf 'encrypted-placeholder\\n' > "$4"
    ;;
  *)
    printf '%s\\n' "$4" >> "$FAKE_UPLOAD_LOG"
    ;;
esac
""",
    )
    environment = _base_environment(fake_bin)
    environment.update(
        {
            "FAKE_COMMAND_LOG": str(command_log),
            "FAKE_STATUS_FILE": str(status_file),
            "FAKE_UPLOAD_LOG": str(upload_log),
        }
    )

    result = subprocess.run(
        ["sh", "scripts/restore_drill_from_s3.sh"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    commands = command_log.read_text(encoding="utf-8")
    assert commands.count("reset-drill-target") == 2
    assert "api.backup verify" in commands
    assert "api.backup restore" in commands
    assert "api.migrations check" in commands
    assert "drills/" in upload_log.read_text(encoding="utf-8")
    assert "target was scrubbed" in result.stdout


def test_render_backup_image_uses_overridable_command() -> None:
    dockerfile = (
        REPOSITORY_ROOT / "docker" / "Dockerfile.backup"
    ).read_text(encoding="utf-8")
    backup_blueprint = (
        REPOSITORY_ROOT / "render.backup.yaml"
    ).read_text(encoding="utf-8")
    drill_blueprint = (
        REPOSITORY_ROOT / "render.restore-drill.yaml"
    ).read_text(encoding="utf-8")

    assert 'CMD ["/app/scripts/backup_to_s3.sh"]' in dockerfile
    assert "ENTRYPOINT" not in dockerfile
    assert "mouvadah-backup-freshness" in backup_blueprint
    assert "BACKUP_MAX_AGE_SECONDS" in backup_blueprint
    assert "mouvadah-monthly-restore-drill" in drill_blueprint
    assert "RESTORE_DRILL_DATABASE_URL" in drill_blueprint
