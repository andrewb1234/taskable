#!/bin/sh
set -eu

: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"
: "${AWS_REGION:?AWS_REGION is required}"

backup_prefix="${BACKUP_S3_PREFIX:-mouvadah/database}"
maximum_age_seconds="${BACKUP_MAX_AGE_SECONDS:-129600}"
status_key="${backup_prefix}/status/latest.json"
work_dir="$(mktemp -d)"
status_file="${work_dir}/latest.json"
backup_file="${work_dir}/backup"
manifest_file="${backup_file}.manifest.json"

cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT INT TERM

aws s3 cp \
  "s3://${BACKUP_S3_BUCKET}/${status_key}" \
  "$status_file" \
  --only-show-errors

object_key="$(
  python3 - "$status_file" "$backup_prefix" "$maximum_age_seconds" <<'PY'
from datetime import UTC, datetime
import json
import sys

status_path, expected_prefix, maximum_age = sys.argv[1:]
with open(status_path, encoding="utf-8") as handle:
    status = json.load(handle)
if status.get("status") != "verified":
    raise SystemExit("latest backup marker is not verified")
object_key = status.get("object_key")
if not isinstance(object_key, str) or not object_key.startswith(
    f"{expected_prefix}/"
):
    raise SystemExit("latest backup marker has an unexpected object key")
if not object_key.endswith(".mouvadah-backup"):
    raise SystemExit("latest backup marker does not reference a backup archive")
created_at = datetime.fromisoformat(status["created_at"].replace("Z", "+00:00"))
age_seconds = int((datetime.now(UTC) - created_at).total_seconds())
if age_seconds < 0:
    raise SystemExit("latest backup marker is dated in the future")
if age_seconds > int(maximum_age):
    raise SystemExit(
        f"latest verified backup is stale ({age_seconds}s > {maximum_age}s)"
    )
print(object_key)
PY
)"

aws s3 cp \
  "s3://${BACKUP_S3_BUCKET}/${object_key}" \
  "$backup_file" \
  --only-show-errors
aws s3 cp \
  "s3://${BACKUP_S3_BUCKET}/${object_key}.manifest.json" \
  "$manifest_file" \
  --only-show-errors

python3 - "$status_file" "$backup_file" "$manifest_file" <<'PY'
import hashlib
import json
import sys

status_path, backup_path, manifest_path = sys.argv[1:]
with open(status_path, encoding="utf-8") as handle:
    status = json.load(handle)
with open(manifest_path, encoding="utf-8") as handle:
    manifest = json.load(handle)
digest = hashlib.sha256()
with open(backup_path, "rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
ciphertext_sha256 = digest.hexdigest()
expected = status.get("ciphertext_sha256")
if ciphertext_sha256 != expected:
    raise SystemExit("backup object hash does not match latest marker")
if manifest.get("ciphertext_sha256") != expected:
    raise SystemExit("backup manifest hash does not match latest marker")
authenticated = manifest.get("authenticated")
if not isinstance(authenticated, dict):
    raise SystemExit("backup manifest lacks authenticated metadata")
for marker_key, manifest_key in (
    ("backup_id", "backup_id"),
    ("created_at", "created_at"),
    ("key_id", "key_id"),
    ("migration_revision", "migration_revision"),
):
    if status.get(marker_key) != authenticated.get(manifest_key):
        raise SystemExit(
            f"backup manifest {manifest_key} does not match latest marker"
        )
PY

echo "latest encrypted backup is fresh and its object integrity matches the marker"
