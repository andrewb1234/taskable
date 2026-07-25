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
* Playwright uses only `web/tests/.e2e-taskable.db`. Its seed helper validates
  that exact resolved SQLite path before deleting or writing anything and
  refuses every other database or dialect.

## Required Test Coverage
1. **CRUD Validation:** Verify project creation, subproject assignment, and ticket generation.
2. **State Transitions:** Test the `PATCH /tickets/{id}` endpoint. Ensure invalid status updates return appropriate `400 Bad Request` HTTP errors.
3. **Agent Capabilities:** Mock the `GITHUB_PAT` and test the MR linking logic. Verify the `GET /agent/context/{id}` payload correctly flattens the subproject context into an LLM-readable string.
4. **SSE Broadcasting:** Intercept the internal event broadcaster to ensure state mutations (like ticket updates) successfully trigger internal event payloads.

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

## GitHub gates

Pull requests and merge-queue candidates run:

- `Required CI`: backend tests on Python 3.12 and 3.14, frontend type/build,
  and authenticated Chromium realtime tests;
- `Required security`: dependency review, Python and npm vulnerability audits,
  and complete-history secret scanning; and
- `Required CodeQL`: Python and JavaScript/TypeScript static analysis.

The aggregate names are intentionally stable so the default-branch ruleset can
require them without coupling policy to a matrix-job display name. All
third-party actions are pinned to full commit SHAs.
