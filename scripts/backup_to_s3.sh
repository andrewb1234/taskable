#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"
: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"
: "${AWS_REGION:?AWS_REGION is required}"

backup_key_id="${BACKUP_KEY_ID:-primary}"
backup_prefix="${BACKUP_S3_PREFIX:-mouvadah/database}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
work_dir="$(mktemp -d)"
backup_file="${work_dir}/${timestamp}.mouvadah-backup"
manifest_file="${backup_file}.manifest.json"
verify_dir="${work_dir}/verify"
object_key="${backup_prefix}/${timestamp}.mouvadah-backup"

cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT INT TERM

mkdir -p "$verify_dir"

python -m api.backup backup \
  --output "$backup_file" \
  --key-id "$backup_key_id"

if [ -n "${BACKUP_S3_KMS_KEY_ID:-}" ]; then
  aws s3 cp "$backup_file" "s3://${BACKUP_S3_BUCKET}/${object_key}" \
    --only-show-errors \
    --sse aws:kms \
    --sse-kms-key-id "$BACKUP_S3_KMS_KEY_ID"
  aws s3 cp "$manifest_file" \
    "s3://${BACKUP_S3_BUCKET}/${object_key}.manifest.json" \
    --only-show-errors \
    --sse aws:kms \
    --sse-kms-key-id "$BACKUP_S3_KMS_KEY_ID"
else
  aws s3 cp "$backup_file" "s3://${BACKUP_S3_BUCKET}/${object_key}" \
    --only-show-errors \
    --sse AES256
  aws s3 cp "$manifest_file" \
    "s3://${BACKUP_S3_BUCKET}/${object_key}.manifest.json" \
    --only-show-errors \
    --sse AES256
fi

aws s3 cp "s3://${BACKUP_S3_BUCKET}/${object_key}" \
  "${verify_dir}/backup" \
  --only-show-errors
aws s3 cp "s3://${BACKUP_S3_BUCKET}/${object_key}.manifest.json" \
  "${verify_dir}/backup.manifest.json" \
  --only-show-errors
python -m api.backup verify --input "${verify_dir}/backup"

etag="$(aws s3api head-object \
  --bucket "$BACKUP_S3_BUCKET" \
  --key "$object_key" \
  --query ETag \
  --output text)"
python -m api.lifecycle purge-due \
  --backup-evidence "s3://${BACKUP_S3_BUCKET}/${object_key}#etag=${etag}"

echo "verified encrypted backup: s3://${BACKUP_S3_BUCKET}/${object_key}"
