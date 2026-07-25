# Infrastructure and Deployment

## Deployment profiles

### Community/local

- FastAPI and React run on one machine.
- SQLite persists at `~/.taskable/taskable.db` or `TASKABLE_DATA_DIR`.
- `MIGRATION_MODE=upgrade` applies ordered Alembic revisions at startup.
- Existing file-backed SQLite databases receive an automatic pre-migration
  backup.
- `python3 bootstrap.py` creates a local owner and revocable per-user API key;
  it never disables authentication.
- Local browser sign-in is available only when `LOCAL_AUTH_ENABLED=true` and
  `FRONTEND_URL` is a loopback origin. The API key is exchanged for an
  HttpOnly session and is not retained by the browser.
- The MCP server runs locally over stdio and reads the same per-user key from
  an owner-only `TASKABLE_CREDENTIALS_FILE`.

### Hosted

- Use managed PostgreSQL, HTTPS, a secret manager, and
  `MIGRATION_MODE=check`.
- Run one migration job before application replicas.
- Do not use application-startup upgrades across multiple replicas.
- Realtime remains process-local and is not ready for multiple API instances
  until the shared-fanout roadmap item ships.

The complete database procedure is in `migrations.md`.

## Environment configuration

Required for hosted operation:

- `DATABASE_URL`: managed PostgreSQL connection URL.
- `FRONTEND_URL`: exact trusted public HTTPS origin.
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
- `JWT_SECRET`: unique random value of at least 32 characters.
- `MIGRATION_MODE=check`.
- `LOCAL_AUTH_ENABLED=false`.
- `DELETION_RECOVERY_DAYS=30` unless an explicitly reviewed 7-90 day policy
  is used.

Optional:

- `CORS_ORIGINS`: explicit trusted origins.
- `AUTH_RATE_LIMIT` / `AUTH_RATE_WINDOW_SECONDS`: per-process login/callback
  sliding-window limit (defaults to 10 requests per 300 seconds per client).
- `ACTION_RATE_LIMIT` / `ACTION_RATE_WINDOW_SECONDS`: per-process unsafe-action
  limit (defaults to 180 requests per 60 seconds per client and credential).
- `GITHUB_PAT`: temporary legacy credential for MR-link lookup.
- `LEGACY_OWNER_EMAIL`: explicit owner for safe adoption of pre-tenancy
  projects.
- `LOCAL_AUTH_ENABLED=true`: loopback community installations only; rejected
  for hosted and non-loopback origins.
- `TASKABLE_CREDENTIALS_FILE`: local MCP credential path. It is not consumed
  by the hosted API.

Never put credentials in container images, repository files, logs, migration
configuration, or frontend build variables.

### Backup Cron Job

The independent backup job is defined separately in `render.backup.yaml` and
uses `docker/Dockerfile.backup`. It needs its own database credential,
application-layer backup-encryption key, and least-privilege S3 credentials.
Do not add those secrets to the static frontend or expose them to the main web
process without a concrete operational need.

The job creates, uploads, downloads, and verifies an encrypted archive before
it is allowed to purge an expired workspace. Apply the S3 lifecycle and IAM
templates in `infra/`, enable bucket public-access blocking, versioning, and
default encryption, and complete an isolated restore drill before describing
production backup as operational. See `recovery.md`.

The application emits CSP, frame-denial, MIME-sniffing, referrer, and
permissions headers on every response; HTTPS deployments also emit one-year
HSTS. Unsafe cookie-authenticated API requests require the exact configured
`FRONTEND_URL` Origin. The built-in limiter is intentionally process-local for
the current single-instance stage; configure a shared edge/application limiter
before adding replicas or claiming denial-of-service resistance.

## Containers

### API

- Base: `python:3.12-slim`.
- Installs `api/requirements.txt`, including Alembic.
- Copies the API package, migration environment, and immutable revisions.
- Exposes port 8000 and runs `uvicorn api.main:app`.
- Persists `/app/data` for the local SQLite profile.

### Web

- Builds with Node 20 Alpine.
- Serves static output from Nginx Alpine.
- Proxies `/api/v1` to the API service.

### Backup

- Base: PostgreSQL 17 Alpine so `pg_dump` and `pg_restore` match the supported
  production major version.
- Adds Python, the API package, and AWS CLI.
- Runs the encrypted backup-to-S3 script as its entrypoint.
- Uses an ephemeral filesystem; retained recovery artifacts exist only in the
  configured object store.

### Compose

`docker/docker-compose.yml` is a local profile. It bind-mounts the host
`~/.taskable` directory rather than hiding SQLite in a named volume. The web
service waits for the API health check. Run `python3 bootstrap.py` before
Compose so the host database contains the local owner and the `.env` contains
the strong JWT secret. Ports 3000 and 8000 bind to `127.0.0.1` only.

## Release procedure

1. Build immutable API and web artifacts from the reviewed commit.
2. Require `Required CI`, `Required security`, and `Required CodeQL` on the
   reviewed commit.
3. Back up the target database and record its identity.
4. Run the single Alembic migration job.
5. Run `python -m api.migrations check`.
6. Deploy API instances with `MIGRATION_MODE=check`.
7. Deploy the web artifact.
8. Verify health, login, tenant isolation, MCP authentication, and one
   reversible write.
9. Record release, migration, and rollback evidence.

For a Render-style single-service deployment, configure the pre-deploy command
as:

```bash
python -m api.migrations upgrade --backup-confirmed \
  && python -m api.migrations check
```

The application must still start with `MIGRATION_MODE=check`. The
`--backup-confirmed` flag is an operator assertion, not a backup mechanism:
verify and record the managed backup before deploying.

The repository supplies protected-CI workflow definitions, dependency update
automation, and stable required-check names. The hosting platform, GitHub
ruleset, and repository action policy remain operational configuration and
must be checked during release. The independent backup job and retention
templates exist, but their production secrets, bucket controls, provider
snapshot schedule, and recurring restore evidence remain control-plane work.
Shared realtime fanout and broader managed infrastructure-as-code remain
absent.
