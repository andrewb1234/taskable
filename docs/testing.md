# Testing and Required CI Gates

## Objective
Prevent unreviewed regressions in the API, frontend, migrations, authenticated
realtime path, and dependency supply chain.

## Dependencies
* `pytest` (Test runner)
* `pytest-asyncio` (Async support)
* `httpx` (Async test client)

## Test Environment Setup
* Override the database engine in tests to use an **in-memory SQLite database** (`sqlite:///:memory:`).
* Ordinary route tests may use `SQLModel.metadata.create_all()` and
  `drop_all()` for isolated fixture speed. Migration tests must build the
  schema only through Alembic and prove revision, upgrade, backup, data
  preservation, fail-closed behavior, and ORM parity.
* `api/tests/test_postgres_migrations.py` runs only with a dedicated loopback
  database named `taskable_test`. It destroys and recreates that database's
  `public` schema, reproduces legacy native-enum drift, applies the repair
  migration, commits real claim/requeue audit actions, creates an encrypted
  PostgreSQL custom archive, and restores it into the dedicated
  `taskable_restore_test` database. The test requires migration head, ORM
  parity, and restored tenant data, then starts two independent broadcaster
  instances and proves PostgreSQL LISTEN/NOTIFY delivers a workspace-tagged
  event across the process boundary.
* `api/tests/test_data_lifecycle.py` proves export hashing and exclusions,
  cross-tenant silence, owner/API-key boundaries, deletion confirmation,
  immediate API-key revocation, in-window restoration, expiry, verified
  tenant purge, and retained non-content lifecycle evidence.
* `api/tests/test_backup.py` proves SQLite authenticated encryption, wrong-key
  and tamper rejection, configured-target safety, full restore, and schema
  parity without needing external services.
* Playwright uses only `web/tests/.e2e-taskable.db`. Its seed helper validates
  that exact resolved SQLite path before deleting or writing anything and
  refuses every other database or dialect.

## Required Test Coverage
1. **CRUD Validation:** Verify project creation, subproject assignment, and ticket generation.
2. **State Transitions:** Test the `PATCH /tickets/{id}` endpoint. Ensure invalid status updates return appropriate `400 Bad Request` HTTP errors.
3. **Agent Capabilities:** Mock the `GITHUB_PAT` and test the MR linking logic. Verify the `GET /agent/context/{id}` payload correctly flattens the subproject context into an LLM-readable string.
4. **SSE Broadcasting:** Verify mutation invalidations, bounded-queue overflow
   resync, event validation, SQLite local mode, reconnect policy, workspace
   authorization, and real cross-process PostgreSQL delivery.

## Local execution

From the repository root:

```bash
.venv/bin/pytest -q
(cd web && npm run lint && npm run build)
(cd web && npm run test:e2e)
(cd web && npm audit --audit-level=high)
.venv/bin/pip-audit -r api/requirements.txt -r mcp/requirements.txt
```

Playwright starts an isolated FastAPI process and Vite server, authenticates a
real browser session, writes through the API, and proves SSE-driven DOM updates.
The PostgreSQL-only regression runs in its own disposable PostgreSQL 17
container in CI; local execution requires an explicit `POSTGRES_TEST_URL` for
the dedicated loopback `taskable_test` database.

## GitHub gates

Pull requests and merge-queue candidates run:

- `Required CI`: backend tests on Python 3.12 and 3.14, frontend type/build,
  a PostgreSQL 17 migration/claim/encrypted-restore/realtime regression, and
  authenticated Chromium realtime tests;
- `Required security`: dependency review, Python and npm vulnerability audits,
  and complete-history secret scanning; and
- `Required CodeQL`: Python and JavaScript/TypeScript static analysis.

The aggregate names are intentionally stable so the default-branch ruleset can
require them without coupling policy to a matrix-job display name. All
third-party actions are pinned to full commit SHAs.
