# Infrastructure and Deployment

## Deployment profiles

### Community/local

- FastAPI and React run on one machine.
- SQLite persists at `~/.taskable/taskable.db` or `TASKABLE_DATA_DIR`.
- `MIGRATION_MODE=upgrade` applies ordered Alembic revisions at startup.
- Existing file-backed SQLite databases receive an automatic pre-migration
  backup.
- The MCP server runs locally over stdio and uses a per-user API key.

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

Optional:

- `CORS_ORIGINS`: explicit trusted origins.
- `GITHUB_PAT`: temporary legacy credential for MR-link lookup.
- `LEGACY_OWNER_EMAIL`: explicit owner for safe adoption of pre-tenancy
  projects.

Never put credentials in container images, repository files, logs, migration
configuration, or frontend build variables.

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

### Compose

`docker/docker-compose.yml` is a local profile. It bind-mounts the host
`~/.taskable` directory rather than hiding SQLite in a named volume. The web
service waits for the API health check.

## Release procedure

1. Build immutable API and web artifacts from the reviewed commit.
2. Run backend tests, frontend build, security scans, and migration tests.
3. Back up the target database and record its identity.
4. Run the single Alembic migration job.
5. Run `python -m api.migrations check`.
6. Deploy API instances with `MIGRATION_MODE=check`.
7. Deploy the web artifact.
8. Verify health, login, tenant isolation, MCP authentication, and one
   reversible write.
9. Record release, migration, and rollback evidence.

The current repository does not yet supply protected CI, managed hosting
infrastructure, shared realtime fanout, or disaster-recovery automation. Those
remain explicit release gates rather than implied guarantees.
