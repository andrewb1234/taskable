# Backup, Restore, Export, and Deletion Runbook

## Status and recovery layers

Mouvadah has two complementary recovery paths:

1. A database-provider snapshot or point-in-time restore path for fast
   operational recovery when that provider feature is enabled.
2. An independent PostgreSQL logical archive encrypted by Mouvadah before it
   is uploaded to object storage.

The repository verifies the second path against PostgreSQL 17 in required CI:
it migrates and seeds a source database, creates an AES-256-GCM archive,
restores it into a fresh database, requires Alembic head and exact ORM parity,
and checks restored tenant data. This is production-like restore evidence, not
evidence that a production backup schedule, provider restore window, RPO, or
RTO is currently configured.

For the hosted Neon database, enable and periodically verify the available
scheduled-snapshot and restore-window controls in the Neon console. Neon
documents encryption and backup behavior in its
[security overview](https://neon.com/docs/security/security-overview) and
[backup schedule API](https://neon.com/docs/changelog/2025-11-07). Provider
snapshots do not replace the independent encrypted archive.

## Backup format and guarantees

`python -m api.backup backup`:

- refuses a database that is not at Alembic head or differs from ORM metadata;
- uses PostgreSQL custom-format `pg_dump` or SQLite's online backup API;
- encrypts the archive as a stream with AES-256-GCM and a random nonce;
- authenticates the format, backup ID, timestamp, database fingerprint,
  migration revision, plaintext hash and size, database-tool version, and key
  ID as additional authenticated data;
- writes the encrypted archive and non-secret manifest with mode `0600`; and
- never places a database password in the archive manifest or command URL.

The manifest is authenticated but not encrypted. It contains operational
metadata such as the database name and a credential-free source fingerprint,
so treat it as internal.

Generate a new 32-byte backup key:

```bash
openssl rand -base64 32
```

Store the result in a secrets manager separately from the database and backup
bucket. `BACKUP_KEY_ID` identifies which escrowed key decrypts an archive.
Key rotation must retain each old key until every backup carrying that key ID
has expired and a newer restore drill has passed.

## Manual backup and verification

```bash
export DATABASE_URL='postgresql://...'
export BACKUP_ENCRYPTION_KEY='base64-encoded-32-byte-key'

python -m api.backup backup \
  --output /secure/path/2026-07-25.mouvadah-backup \
  --key-id recovery-2026-07

python -m api.backup verify \
  --input /secure/path/2026-07-25.mouvadah-backup
```

Keep the adjacent
`2026-07-25.mouvadah-backup.manifest.json` file with the archive. Verification
checks the ciphertext hash and size, AES-GCM authentication, plaintext hash,
and archive structure. It does not prove that the archive can meet an RTO;
only a timed restore drill does that.

## Scheduled independent backup

`docker/Dockerfile.backup` and `scripts/backup_to_s3.sh` define the isolated
backup runner. `render.backup.yaml` is a separate Cron Job blueprint so
adopting it cannot replace the existing web-service definition accidentally.
Configure its `sync: false` secrets in the Render dashboard.

The daily job:

1. creates a fresh encrypted archive in an owner-only temporary directory;
2. uploads the archive and manifest to the configured S3 prefix;
3. applies S3 KMS encryption when `BACKUP_S3_KMS_KEY_ID` is configured,
   otherwise S3-managed AES-256 encryption;
4. downloads both objects into a second path and verifies the downloaded copy;
5. records the uploaded object's URI and ETag as backup evidence; and
6. only then purges workspaces whose recovery windows have expired.

The shell exits on the first failure. A failed backup, upload, download, or
verification therefore prevents permanent workspace purge.
Render serializes runs of one Cron Job; enable workspace email or Slack
notifications for cron-run failures and treat any missed daily success as an
operator alert.

Required job secrets:

- `DATABASE_URL`
- `BACKUP_ENCRYPTION_KEY`
- `BACKUP_S3_BUCKET`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`

Optional settings are `BACKUP_KEY_ID`, `BACKUP_S3_PREFIX`, and
`BACKUP_S3_KMS_KEY_ID`. Give the job a dedicated least-privilege AWS identity.
`infra/s3-backup-iam-policy.json` is the object-prefix policy template; add the
narrow KMS permissions in `infra/s3-backup-kms-iam-policy.json` only when a
customer-managed KMS key is selected.

Enable bucket public-access blocking, versioning, default encryption, and the
lifecycle in `infra/s3-backup-lifecycle.json`. Current backup objects expire
after 35 days; versions made noncurrent by expiration remain for at most seven
additional days. The 35-day current-object window covers the default 30-day
workspace recovery period with a five-day operational buffer. Changing
`DELETION_RECOVERY_DAYS` requires reviewing retention so the independent
backup always outlives the recovery window.

## Restore drill

Restore into a fresh, isolated database first. Do not point application
traffic at it until verification is complete.

```bash
python -m api.backup verify \
  --input /secure/path/2026-07-25.mouvadah-backup

python -m api.backup restore \
  --input /secure/path/2026-07-25.mouvadah-backup \
  --target-url 'postgresql://.../mouvadah_restore_drill' \
  --confirm-database mouvadah_restore_drill

DATABASE_URL='postgresql://.../mouvadah_restore_drill' \
  python -m api.migrations check
```

The restore command:

- requires the exact target database name as a confirmation;
- refuses a backend mismatch;
- refuses the configured application database by default;
- restores PostgreSQL in one transaction with ownership and grants excluded;
  and
- rejects the result unless it is at migration head and matches ORM metadata.

Restoring over the configured application target additionally requires
`--allow-configured-target` and separate `--backup-evidence`. That escape hatch
is for a reviewed incident procedure after writes are stopped, the exact
target is independently identified, and a second verified backup exists. It
is not the normal drill path.

Record for every drill:

- archive URI, backup ID, key ID, ciphertext SHA-256, and source fingerprint;
- source and isolated-target identities;
- application commit and migration revision;
- operator and reviewer;
- download, verification, restore-start, restore-finish, and smoke-test times;
- integrity, schema-parity, authentication, tenant-count, and sampled-data
  results;
- measured data-loss window and recovery duration; and
- cleanup confirmation for the isolated target.

Run quarterly during private beta and monthly before paid general
availability. Publish no RPO, RTO, or SLA until several production-environment
drills establish repeatable results.

## Workspace export

An owner using an interactive browser session can download a canonical
workspace export from Profile → Data & Recovery or:

```text
GET /api/v1/workspaces/{workspace_id}/export
```

The response is `no-store`, includes
`X-Mouvadah-Export-SHA256`, and records an `EXPORTED` lifecycle event.
It includes workspace members and user profiles, projects, subprojects,
tickets, dependencies, comments, ticket audit rows, knowledge and proposals,
agent sessions, API-key metadata and restrictions, and prior workspace
lifecycle events.

It excludes API-key hashes and full keys, browser sessions, OAuth and server
configuration, database credentials, and backup keys. Exports contain customer
content and identity data; protect them like database backups.

## Recoverable workspace deletion

Only an owner in an interactive browser session can schedule deletion.
Scheduling requires:

- a workspace export generated during the preceding 24 hours;
- that export's exact SHA-256; and
- the exact workspace slug as typed confirmation.

The workspace is immediately hidden from project and descendant routes, every
workspace API key is revoked, and a `DELETION_SCHEDULED` event records the
export hash and purge deadline. The workspace remains visible in Profile →
Data & Recovery and is restorable until `purge_after`. Restoring does not
reactivate API keys.

After the window expires, the verified backup job runs:

```bash
python -m api.lifecycle purge-due \
  --backup-evidence 's3://bucket/prefix/archive#etag=...'
```

The purge deletes the workspace graph child-first, verifies that the workspace
is gone, and retains a content-free `PURGED` lifecycle ledger containing the
backup evidence and deletion counts. The ledger deliberately has no foreign
keys so it survives tenant removal.

The final pre-purge archive still contains the workspace and follows normal
backup rotation. With the supplied versioned-bucket lifecycle, that archive is
no longer current after 35 days and its noncurrent version is removed within
seven additional days. Therefore the default maximum is 30 days in the live
recovery window plus up to 42 days in independent backup retention. Provider
snapshot retention is separate and must be disclosed from the actual Neon
configuration.

Project, subproject, ticket, and knowledge-node delete endpoints remain
immediate hard deletes. Do not present workspace recovery as undo protection
for those object-level actions; approval policies for destructive agent
actions remain a separate product gap.

## Incident order of operations

For data corruption or accidental deletion:

1. stop or isolate writes and record the incident time;
2. preserve logs and identify the exact database and affected workspace;
3. prefer in-window workspace restoration when applicable;
4. choose provider point-in-time recovery or the independent archive based on
   the failure mode;
5. restore to an isolated target and verify before any cutover;
6. review tenant counts and sampled records without exposing unrelated tenant
   content;
7. perform a reviewed cutover or selective recovery;
8. rotate any credential that may have been exposed; and
9. record measured recovery evidence and follow-up actions.
