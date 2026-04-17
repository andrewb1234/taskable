# Learnings Ledger

> Append-only record of frictions, divergences, and workarounds encountered while building Taskable.
> Protocol: read this file at the start of every session before mutating code. Never rewrite history — only append.

## Entry Format
Each entry MUST use this template:

```
### [ISO-8601 Timestamp] — [Short Title]
- **Context:** What operation was being attempted.
- **Friction:** The specific error, block, or hallucination.
- **Resolution:** The technical solution and reasoning.
```

## When to Append
- Resolving a complex bug, race condition, or framework limitation.
- Making an architectural divergence from the original specifications.
- Discovering a specific workaround for local Docker or MCP stdio networking.

---

## Entries

### 2026-04-17T07:02:00Z — Ledger Initialized
- **Context:** Pre-build ingestion of `docs/index.md`, `docs/prd.md`, `docs/folder_navigation.md`, and `docs/protocol.md` before scaffolding the Taskable Co-Pilot Workspace.
- **Friction:** None. Initialization step per `protocol.md`.
- **Resolution:** Created `learnings.md` with an explicit entry format so future sessions can append deterministically. Subsequent entries will follow the template above.

### 2026-04-17T07:10:00Z — Python 3.14 vs. pinned pydantic-core
- **Context:** First `pip install -r api/requirements.txt` on local Python 3.14.0 while bringing up the FastAPI scaffold.
- **Friction:** `pydantic==2.10.3` depends on `pydantic-core==2.27.x`, whose Rust/PyO3 build caps at Python 3.13: `error: the configured Python interpreter version (3.14) is newer than PyO3's maximum supported version (3.13)`.
- **Resolution:** Switched to inclusive version ranges (`pydantic>=2.11,<3`, `pydantic-core` resolved to 2.46.1) which ship prebuilt 3.14 wheels. Kept FastAPI/SQLModel on the latest compatible releases. This keeps the project forward-compatible without forcing users onto Python 3.11.

### 2026-04-17T07:12:00Z — Divergence: UI is unauthenticated on localhost
- **Context:** `docs/api_endpoints.md` declares the bearer token `(Agent only)`, but the React client writes via the same REST endpoints.
- **Friction:** Spec does not say how the UI authenticates.
- **Resolution:** Chose option (a): the bearer guard only applies to the `/agent/*` routes (explicitly Agent-only per the spec's "Agent Integrations" section). Mutation routes inspect the `Authorization` header softly to tag the audit log `actor` as `AGENT` vs `HUMAN`. Logged so we don't regress to per-request auth later.

### 2026-04-17T07:12:30Z — Divergence: `GET /tickets/{id}` added
- **Context:** `docs/client_server.md` assumes the UI can targeted-refetch with `GET /tickets/42`, but that route is missing from `docs/api_endpoints.md`.
- **Friction:** Implementing the SSE refetch lifecycle required this route.
- **Resolution:** Added `GET /tickets/{id}` returning a `TicketDetail` (ticket + ordered comments + audit log). Treated as an implicit requirement of the SSE refetch contract, not a scope expansion.

### 2026-04-17T07:13:00Z — Decision: `utcnow()` helper replaces `datetime.utcnow`
- **Context:** Schema spec says default `datetime.utcnow`. Python 3.12+ deprecates it.
- **Friction:** Direct use would spam DeprecationWarnings during tests.
- **Resolution:** Added `api/utils/time.py::utcnow()` returning a timezone-naive UTC datetime via `datetime.now(timezone.utc).replace(tzinfo=None)`. One-line swap if we later want timezone-aware storage.

### 2026-04-17T07:22:00Z — SQLAlchemy mapper vs PEP 563 string annotations
- **Context:** First pytest run after scaffolding the API surface. All 16 DB-touching tests failed identically.
- **Friction:** `sqlalchemy.exc.InvalidRequestError: ... expression "relationship("list['Subproject']")" seems to be using a generic class as the argument to relationship()`. Cause: `from __future__ import annotations` converts `list["Subproject"]` into a literal string, and SQLAlchemy's relationship introspection cannot unwrap stringified generics at class construction time.
- **Resolution:** Removed `from __future__ import annotations` from `api/models/entities.py` and switched to `typing.List[...]`. Kept the future import elsewhere where it helps. Added a header comment so future edits don't re-introduce the import. 17/17 API tests now green.

### 2026-04-17T07:35:00Z — Folder-name collision: `mcp/` vs installed `mcp` package
- **Context:** After `pip install mcp>=1.1`, attempted `python -c "import mcp.mcp_server"` to smoke-test tool definitions.
- **Friction:** `ModuleNotFoundError: No module named 'mcp.mcp_server'` because our local `mcp/` directory has no `__init__.py` so it isn't a package; Python resolves `mcp` to the installed SDK instead.
- **Resolution:** Don't make `mcp/` a package. Invoke `python mcp/mcp_server.py` directly (Python prepends the script's directory to `sys.path`, so `import mcp` still resolves to the installed SDK). Documented in `mcp/README.md`. If we ever need to import the server module programmatically, do `sys.path.insert(0, "mcp"); import mcp_server`.

### 2026-04-17T07:13:30Z — Decision: MR route is attach-only for MVP
- **Context:** `POST /tickets/{id}/mr` is described as "attach MR link or trigger branch generation."
- **Friction:** Scope of branch generation is undefined; `GITHUB_PAT` is mentioned but MCP tool `link_mr` only attaches.
- **Resolution:** MVP implements attach-only. Writes `AuditAction.MR_LINKED` and emits `SSEAction.MR_LINKED`. Branch creation can be added later behind a `GITHUB_PAT`-gated helper without changing the route contract.
