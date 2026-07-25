# Database Migration Runbook

Mouvadah uses Alembic as the only release-schema mechanism. Application
startup no longer calls `SQLModel.metadata.create_all()` or executes ad-hoc
`ALTER TABLE` statements.

## Supported database states

The migration bootstrap recognizes exactly these states:

1. An empty database.
2. The unversioned 0.1.0 pre-tenancy schema at revision
   `0001_pre_tenancy`.
3. An unversioned development database that already contains workspace
   tenancy tables and `Project.workspace_id`.
4. A database carrying a known Alembic revision.

Unknown databases and partial workspace migrations fail closed before any
schema mutation. Do not manually stamp a rejected database. Restore a verified
backup or write a reviewed repair revision for the exact schema.

## Local development and Community

`MIGRATION_MODE=upgrade` is the local default. API startup applies pending
revisions. When an existing file-backed SQLite database needs a mutation, the
runner first creates a consistent SQLite backup beside it:

```text
taskable.db.pre-migration-<UTC timestamp>.bak
```

Useful operator commands:

```bash
# Apply ordered revisions.
python -m api.migrations upgrade

# Print the database revision.
python -m api.migrations current

# Require migration head and exact ORM schema parity.
python -m api.migrations check
```

In-memory and empty SQLite databases do not need a backup.

## Hosted PostgreSQL deployment

Application instances must run with `MIGRATION_MODE=check`. Production
configuration validation rejects startup-upgrade mode so multiple replicas
cannot race to change the schema.

For each release:

1. Stop writes or enter the deployment's documented maintenance mode.
2. Create a managed snapshot or logical backup.
3. Verify the backup exists, is encrypted, and belongs to the exact target
   database and release.
4. Run one migration job:

   ```bash
   DATABASE_URL=<postgres-url> \
   MIGRATION_MODE=check \
   python -m api.migrations upgrade --backup-confirmed
   ```

5. Run the release gate:

   ```bash
   DATABASE_URL=<postgres-url> \
   MIGRATION_MODE=check \
   python -m api.migrations check
   ```

6. Start application instances with `MIGRATION_MODE=check`.
7. Verify health, authentication, a workspace-scoped read, and a reversible
   write.
8. Record the revision, backup identity, release commit, operator, timestamps,
   and verification result.

The `--backup-confirmed` flag is mandatory when an existing non-SQLite
database needs an upgrade. It is evidence supplied by the operator, not a
backup implementation.

### Revision 0004 operational note

Revision `0004_session_key_security` creates the browser-session ledger and
adds API-key workspace, scope, and project restrictions. Existing API keys
owned by a user with exactly one workspace are bound to that workspace with
read/write scope; keys with zero or multiple possible workspaces are revoked
and must be reissued. Existing browser cookies do not contain a server-side
session ID, so users must sign in once after this release.

### Revision 0005 operational note

Revision `0005_audit_action_enum_values` repairs pre-Alembic PostgreSQL
databases whose native `auditaction` type predates `TICKET_CLAIMED` and
`TICKET_REQUEUED`. Previously, Alembic column/type comparison did not compare
native enum members, so the ORM parity gate did not expose this drift. The
release gate now compares PostgreSQL enum labels explicitly. CI also reproduces
the legacy enum, applies the migration, checks the actual `pg_enum` members,
and commits claim/requeue audit records. SQLite needs no repair because it
stores these enum values as strings.

## Failure and rollback policy

If migration or parity verification fails:

- do not start the new application release;
- do not edit `alembic_version`;
- retain the error and database logs;
- restore the pre-migration backup when any non-transactional or uncertain
  change may have occurred; and
- prefer a reviewed forward-fix revision when the database transaction rolled
  back cleanly.

Revision downgrade functions exist for development verification, but production
rollback is an application-and-data decision. Never assume a database
downgrade is lossless. Restore from the verified snapshot when a revision
removes or transforms data.

## Authoring schema changes

1. Change the SQLModel metadata.
2. Add an immutable revision under `api/migrations/versions/`.
3. Exercise upgrade from every supported prior revision.
4. Test data preservation and fail-closed behavior.
5. Run `python -m api.migrations check` on fresh SQLite and PostgreSQL.
6. Add the migration result to release evidence.

Alembic autogenerate is a review aid, not an approval mechanism. Inspect every
generated operation, constraint, index, default, and data backfill.
