# Mouvadah — Human-Agent Control Plane

A local-first control and memory plane for **human-agent software delivery**.
Humans work in the React UI, agents work through MCP, and both use the same
FastAPI state machine for durable project context, dependency-safe execution,
reviewable knowledge, and handoffs across short-lived agent sessions.
Real-time updates flow back to the UI through Server-Sent Events.

> Full specifications live in [`docs/`](./docs). Architectural decisions and frictions are logged in [`learnings.md`](./learnings.md).
> The current company direction, offerings, competitive position, and release
> gates live in [`docs/company_blueprint.md`](./docs/company_blueprint.md).
> Verified security controls and explicit non-guarantees live in
> [`docs/security_and_trust.md`](./docs/security_and_trust.md).

## Architecture

```
┌──────────┐   REST + SSE    ┌─────────────┐   HTTP (bearer)   ┌─────────────┐
│ React UI │◄───────────────►│  FastAPI +  │◄──────────────────│ MCP stdio   │
│ (Vite)   │                 │  SQLModel + │                   │ server      │
│  :5173   │                 │  SQLite     │                   │ (agent)     │
└──────────┘                 │   :8000     │                   └─────────────┘
                             └─────────────┘
                                    │
                                    ▼
                          ~/.taskable/taskable.db
```

- `api/` — FastAPI backend (SQLModel entities, routes, SSE broadcaster, pytest).
- `web/` — Vite + React + Tailwind UI with `useSSE` reactive refetch.
- `mcp/` — Python MCP stdio server exposing the agent tool catalogue.
- `docker/` — two-service docker-compose stack.

## Agent authentication

The current authenticated flow uses a per-user Mouvadah API key:

1. Sign in through the web application.
2. Open the profile page and create an API key.
3. Put the returned one-time value in the MCP process as
   `TASKABLE_API_KEY` (the legacy `AGENT_API_KEY` variable is also read).
4. Revoke or replace the key from the profile page when needed.

## Zero-Config Setup

> **Alpha limitation:** `bootstrap.py` still provisions the legacy shared
> `AGENT_API_KEY`; it does not provision Google OAuth or a database-backed
> per-user API key. It is not a complete fresh-install path for the current
> authenticated application. This is tracked as a release blocker in the
> company and security blueprints.

From a clean clone:

```bash
python3 bootstrap.py
```

This script will:

1. Create `.venv/` and install all backend + MCP dependencies
2. Generate a legacy `AGENT_API_KEY` (or accept one you paste in)
3. Write `.env` at the repo root
4. Detect `~/.codeium/windsurf/mcp_config.json` and merge in a `taskable` server block with absolute paths — preserving your existing entries
5. Print the next-step commands

If you'd rather wire things up manually, follow the *Quick Start (local dev)* section below.

## Quick Start (local dev, no Docker)

### 1. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt

cp .env.example .env       # then edit AGENT_API_KEY (see explanation above)

uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

The SQLite database lives at `~/.taskable/taskable.db` by default — survives
`git clean`, is easy to back up, and is inspectable with any SQLite GUI. Local
startup applies ordered Alembic revisions and creates a timestamped
pre-migration backup before changing an existing file-backed database. See
[`docs/migrations.md`](./docs/migrations.md) for hosted PostgreSQL and rollback
procedures.

Visit `http://127.0.0.1:8000/docs` for the OpenAPI explorer.

### 2. Frontend

```bash
cd web
npm install
npm run dev   # http://127.0.0.1:5173
```

The Vite dev server proxies `/api/v1/*` to `http://localhost:8000`, so the UI works without CORS or env setup.

### 3. MCP Agent Server

Pick **one** of three install styles:

```bash
# Option A — same venv as the API (simplest)
pip install -r mcp/requirements.txt
TASKABLE_API_KEY=<key-created-in-profile> python mcp/mcp_server.py

# Option B — global isolated install via pipx (recommended for IDE use)
pipx install ./mcp
AGENT_API_KEY=<same as .env> taskable-mcp

# Option C — uv tool (if you live in uv-land)
uv tool install ./mcp
AGENT_API_KEY=<same as .env> taskable-mcp
```

Options B and C produce a `taskable-mcp` console script on your `$PATH` so the Windsurf MCP config can use a stable command instead of an absolute venv-relative Python path. Hook it into Windsurf by copying [`mcp/mcp.json.example`](./mcp/mcp.json.example) into your Windsurf MCP config (typically `~/.codeium/windsurf/mcp_config.json`) — or run `python3 bootstrap.py` to do it automatically.

## Quick Start (Docker)

```bash
cp .env.example .env       # fill in AGENT_API_KEY
docker compose -f docker/docker-compose.yml up --build
```

- API: `http://localhost:8000`
- UI: `http://localhost:3000`
- SQLite persisted on the **host** at `~/.taskable/taskable.db` via a bind mount (back up, copy, or inspect with any desktop tool — no `docker exec` needed).

The MCP server is **not** containerized — it runs on the host via stdio per `docs/deployment.md`, and points at `http://localhost:8000/api/v1` via the published API port.

## Testing

```bash
# Backend (unit + agent simulator subprocess)
pytest api/tests/ -v

# Migration head and ORM schema parity for DATABASE_URL
python -m api.migrations check

# Frontend type-check + production build
cd web && npm run build

# End-to-end SSE realtime test (boots API + UI, drives Chromium)
cd web && npx playwright install chromium  # one-time
cd web && npm run test:e2e
```

The pytest suite covers CRUD, state transitions, agent endpoints, and SSE broadcasting against an isolated in-memory SQLite. The `test_mcp_simulator.py` module spawns a real `uvicorn` + `mcp_server.py` subprocess pair and exercises the full JSON-RPC handshake against a temp SQLite — proving the MCP wire protocol end-to-end. The Playwright spec then proves that an `agent`-side PATCH propagates to the live React DOM in under one second via SSE.

Quick aliases via the `Makefile`:

```bash
make bootstrap    # python3 bootstrap.py
make dev          # spin up API + UI in two background tabs
make seed         # load demo project/subproject/tickets
make test         # pytest
make e2e          # playwright realtime spec
```

## API surface (v1)

| Verb   | Path                                                | Notes                         |
| ------ | --------------------------------------------------- | ----------------------------- |
| GET    | `/api/v1/workspaces`                                | Caller memberships and roles. |
| POST   | `/api/v1/workspaces`                                | Creates an owned workspace.   |
| GET    | `/api/v1/workspaces/{id}/members`                   | OWNER/ADMIN only.             |
| GET    | `/api/v1/projects`                                  |                               |
| POST   | `/api/v1/projects`                                  |                               |
| GET    | `/api/v1/projects/{id}`                             |                               |
| DELETE | `/api/v1/projects/{id}`                             | Cascades subprojects + knowledge. |
| GET    | `/api/v1/projects/{id}/subprojects`                 |                               |
| POST   | `/api/v1/projects/{id}/subprojects`                 |                               |
| GET    | `/api/v1/subprojects/{id}`                          | Returns nested tickets.       |
| PATCH  | `/api/v1/subprojects/{id}`                          |                               |
| DELETE | `/api/v1/subprojects/{id}`                          | Cascades tickets + audit.     |
| POST   | `/api/v1/subprojects/{id}/tickets`                  |                               |
| GET    | `/api/v1/tickets/{id}`                              | Nested comments + audit logs. |
| PATCH  | `/api/v1/tickets/{id}`                              | Writes audit entries.         |
| DELETE | `/api/v1/tickets/{id}`                              | Cascades comments + audit.    |
| POST   | `/api/v1/tickets/{id}/mr`                           | Attach MR, emits `MR_LINKED`. |
| GET    | `/api/v1/tickets/{id}/comments`                     |                               |
| POST   | `/api/v1/tickets/{id}/comments`                     |                               |
| GET    | `/api/v1/projects/{id}/knowledge`                   | Flat list; client builds tree.|
| GET    | `/api/v1/projects/{id}/knowledge/context-trail`     | Query-scored knowledge trail. |
| POST   | `/api/v1/projects/{id}/knowledge`                   | Creates a `KnowledgeNode`.    |
| GET    | `/api/v1/knowledge/{id}`                            | Single node detail.           |
| PATCH  | `/api/v1/knowledge/{id}`                            | Re-parent / retype / edit.    |
| DELETE | `/api/v1/knowledge/{id}`                            | Cascades to descendants.      |
| GET    | `/api/v1/events`                                    | SSE stream (heartbeat 15s).   |
| GET    | `/api/v1/agent/context/{id}`                        | **Bearer required.**          |
| GET    | `/api/v1/agent/projects/{id}/knowledge`             | **Bearer required** (outline).|
| GET    | `/api/v1/agent/projects/{id}/context-trail`         | **Bearer required** (trail).  |
| GET    | `/api/v1/agent/knowledge/{id}`                      | **Bearer required** (detail). |

### Knowledge tree (upstream of tickets)

Each project owns a tree of `KnowledgeNode` entries — `RAW` pastes, `SUMMARY`
compressions, and drafted `PRD` / `TDD` specifications — that sits between "I
have an idea" and "break it into tickets." The agent drives it through MCP
tools (`list_knowledge_nodes`, `find_context_trail`, `read_knowledge_node`,
`create_knowledge_node`, `update_knowledge_node`); the human reviews and edits the same nodes in the
`Workspace` **Knowledge** tab. Mutations broadcast
`KNOWLEDGE_NODE_CREATED|UPDATED|DELETED` over SSE so the tree panel stays live
without a reload. Design rationale and friction log: `learnings.md`.

### Context trails

The Knowledge tab includes a **Find context trail** box. A human or agent can
query a task intent like `battle component`; Taskable scores the knowledge tree,
returns a suggested load order, and shows matched branches with child hints. The
MCP tool `find_context_trail` exposes the same trail to fresh agent windows so
they can load scoped memory instead of rereading the whole project.

The trail UI can also save a **Context checkpoint** node with `node:<id>`
breadcrumbs for everything loaded. When the human sees stale or incorrect
context, the node editor's **Correction request** box creates a child summary
under the bad node so the agent can find and resolve it later.

`GET /tickets/{id}` was added beyond the original spec so the client-side SSE-driven targeted refetch described in `docs/client_server.md` has a route to hit. Logged in `learnings.md`.

### Resizable panels

Three draggable gutters let the human reshape the layout:

- **Sidebar ↔ workspace** — horizontal, persisted as `taskable.sidebar.width`.
- **Knowledge tree ↔ editor** — horizontal, persisted as `taskable.knowledge.treeWidth`.
- **Subproject header ↔ Kanban** — vertical, persisted as `taskable.kanban.headerHeight`.

All three share one primitive, `ResizableSplit` (`web/src/components/ui/resizable-split.tsx`),
which is dependency-free and stores sizes in `localStorage`. Min/max bounds
keep panes from collapsing past usefulness.

### Deletion

Every layer (project, subproject, ticket, knowledge node) supports hard
delete via the REST API, MCP tools (`delete_project`, `delete_subproject`,
`delete_ticket`, `delete_knowledge_node`), and hover-revealed trash icons in
the UI. Deletes cascade through SQLModel relationships and broadcast
`PROJECT_DELETED | SUBPROJECT_DELETED | TICKET_DELETED | KNOWLEDGE_NODE_DELETED`
over SSE so other panes reconcile immediately.

### Live source-reference chips

Knowledge-node `source_refs` entries of the form `node:<id>` render above the
textarea as clickable pills showing the target node's live title and type
badge. Clicking a pill selects that node; if the referenced node has been
deleted, the pill turns red and is marked `GONE`. Non-`node:` entries (file
paths, URLs) render as muted monospace chips.

## Auth model

- **UI:** Google authorization-code sign-in issues an HttpOnly session cookie.
- **MCP server:** Injects a per-user API key as an Authorization bearer token.
- **Audit attribution:** Cookie-authenticated writes are currently tagged
  `HUMAN`; API-key writes are tagged `AGENT`.
- **Tenant boundary:** Projects belong to workspaces, descendants inherit that
  boundary, and centralized authorization checks the caller's membership.
  Ambiguous legacy projects fail closed until an owner is configured.
- **Alpha boundary:** Do not expose the current build as a production public
  SaaS. Browser-session revocation, complete CSRF defense, rate limiting,
  shared realtime, recovery automation, and protected delivery remain open.
  See `docs/security_and_trust.md`.

## Working directory layout

```
taskable/
├── api/                # FastAPI app + SQLModel + pytest suite
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── events.py
│   ├── schemas.py
│   ├── models/
│   ├── routes/
│   ├── tests/
│   └── utils/
├── web/                # Vite + React + Tailwind UI
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── vite.config.ts
├── mcp/                # MCP stdio server
│   ├── mcp_server.py
│   ├── mcp.json.example
│   └── README.md
├── docker/             # Dockerfile.api, Dockerfile.web, compose, nginx
├── docs/               # Product + architecture specs (read-only)
├── learnings.md        # Append-only ledger of decisions / frictions
└── README.md
```

## Working on this codebase

Read `docs/protocol.md` and `learnings.md` before every non-trivial change. Commit functional milestones individually (`feat(scope): description`). Append every divergence or workaround to `learnings.md`.
