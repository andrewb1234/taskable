#!/bin/sh
set -eu

: "${RESTORE_DRILL_DATABASE_URL:?RESTORE_DRILL_DATABASE_URL is required}"
: "${RESTORE_DRILL_CONFIRM_DATABASE:?RESTORE_DRILL_CONFIRM_DATABASE is required}"
: "${RESTORE_DRILL_PROTECTED_DATABASE_FINGERPRINT:?RESTORE_DRILL_PROTECTED_DATABASE_FINGERPRINT is required}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"
: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"
: "${AWS_REGION:?AWS_REGION is required}"

backup_prefix="${BACKUP_S3_PREFIX:-mouvadah/database}"
status_key="${backup_prefix}/status/latest.json"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
drill_result_key="${backup_prefix}/drills/${timestamp}.json"
work_dir="$(mktemp -d)"
status_file="${work_dir}/latest.json"
backup_file="${work_dir}/backup"
manifest_file="${backup_file}.manifest.json"
result_file="${work_dir}/restore-drill.json"
target_needs_scrub=0

cleanup() {
  original_status="$?"
  trap - EXIT INT TERM
  scrub_status=0
  if [ "$target_needs_scrub" -eq 1 ]; then
    python3 -m api.backup reset-drill-target \
      --target-url "$RESTORE_DRILL_DATABASE_URL" \
      --confirm-database "$RESTORE_DRILL_CONFIRM_DATABASE" \
      --protected-database-fingerprint \
        "$RESTORE_DRILL_PROTECTED_DATABASE_FINGERPRINT" || scrub_status="$?"
  fi
  rm -rf "$work_dir"
  if [ "$original_status" -ne 0 ]; then
    exit "$original_status"
  fi
  exit "$scrub_status"
}
trap cleanup EXIT INT TERM

upload_encrypted() {
  source_path="$1"
  destination_uri="$2"
  if [ -n "${BACKUP_S3_KMS_KEY_ID:-}" ]; then
    aws s3 cp "$source_path" "$destination_uri" \
      --only-show-errors \
      --sse aws:kms \
      --sse-kms-key-id "$BACKUP_S3_KMS_KEY_ID"
  else
    aws s3 cp "$source_path" "$destination_uri" \
      --only-show-errors \
      --sse AES256
  fi
}

aws s3 cp \
  "s3://${BACKUP_S3_BUCKET}/${status_key}" \
  "$status_file" \
  --only-show-errors

object_key="$(
  python3 - \
    "$status_file" \
    "$backup_prefix" \
    "$RESTORE_DRILL_CONFIRM_DATABASE" <<'PY'
import json
import sys

status_path, expected_prefix, target_database = sys.argv[1:]
if not target_database.startswith("mouvadah_restore_drill"):
    raise SystemExit(
        "RESTORE_DRILL_CONFIRM_DATABASE must start with "
        "'mouvadah_restore_drill'"
    )
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

python3 -m api.backup verify --input "$backup_file"

python3 -m api.backup reset-drill-target \
  --target-url "$RESTORE_DRILL_DATABASE_URL" \
  --confirm-database "$RESTORE_DRILL_CONFIRM_DATABASE" \
  --protected-database-fingerprint \
    "$RESTORE_DRILL_PROTECTED_DATABASE_FINGERPRINT"
target_needs_scrub=1

restore_started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
restore_started_epoch="$(date -u +%s)"
python3 -m api.backup restore \
  --input "$backup_file" \
  --target-url "$RESTORE_DRILL_DATABASE_URL" \
  --confirm-database "$RESTORE_DRILL_CONFIRM_DATABASE" \
  --protected-database-fingerprint \
    "$RESTORE_DRILL_PROTECTED_DATABASE_FINGERPRINT"
DATABASE_URL="$RESTORE_DRILL_DATABASE_URL" \
  python3 -m api.migrations check
restore_finished_epoch="$(date -u +%s)"
restore_finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 -m api.backup reset-drill-target \
  --target-url "$RESTORE_DRILL_DATABASE_URL" \
  --confirm-database "$RESTORE_DRILL_CONFIRM_DATABASE" \
  --protected-database-fingerprint \
    "$RESTORE_DRILL_PROTECTED_DATABASE_FINGERPRINT"
target_needs_scrub=0

python3 - \
  "$status_file" \
  "$RESTORE_DRILL_CONFIRM_DATABASE" \
  "$restore_started_at" \
  "$restore_finished_at" \
  "$restore_started_epoch" \
  "$restore_finished_epoch" > "$result_file" <<'PY'
from datetime import UTC, datetime
import json
import sys

(
    status_path,
    target_database,
    restore_started_at,
    restore_finished_at,
    restore_started_epoch,
    restore_finished_epoch,
) = sys.argv[1:]
with open(status_path, encoding="utf-8") as handle:
    status = json.load(handle)
backup_created_at = datetime.fromisoformat(
    status["created_at"].replace("Z", "+00:00")
)
started_at = datetime.fromisoformat(
    restore_started_at.replace("Z", "+00:00")
)
result = {
    "backup_created_at": status["created_at"],
    "backup_id": status["backup_id"],
    "ciphertext_sha256": status["ciphertext_sha256"],
    "key_id": status["key_id"],
    "migration_revision": status["migration_revision"],
    "observed_recovery_duration_seconds": (
        int(restore_finished_epoch) - int(restore_started_epoch)
    ),
    "observed_recovery_point_age_seconds": int(
        (started_at.astimezone(UTC) - backup_created_at).total_seconds()
    ),
    "restore_finished_at": restore_finished_at,
    "restore_started_at": restore_started_at,
    "schema_parity": "verified",
    "status": "passed",
    "target_database": target_database,
    "target_scrubbed": True,
}
print(json.dumps(result, separators=(",", ":"), sort_keys=True))
PY

upload_encrypted \
  "$result_file" \
  "s3://${BACKUP_S3_BUCKET}/${drill_result_key}"

echo "isolated restore drill passed and target was scrubbed"
echo "restore drill evidence: s3://${BACKUP_S3_BUCKET}/${drill_result_key}"
