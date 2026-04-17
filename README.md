# Taskable — Co-Pilot Workspace

A local-first task management system designed for **synchronous collaboration between a human developer and an AI agent**. It acts as a shared state machine for project execution: humans work in the React UI, agents work through the MCP server, and both talk to the same FastAPI core over REST. Real-time updates flow back to the UI via Server-Sent Events.

> Full specifications live in [`docs/`](./docs). Architectural decisions and frictions are logged in [`learnings.md`](./learnings.md).

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
- `mcp/` — Python MCP stdio server exposing 5 agent tools.
- `docker/` — two-service docker-compose stack.

## What is `AGENT_API_KEY`?

A **single shared secret** that you generate locally — it is **not** issued by any third party (no Anthropic / OpenAI / GitHub account needed).

- It guards the `/api/v1/agent/*` routes so a curious browser tab cannot pretend to be the agent.
- The same string must appear in **two places**:
  1. `.env` (read by the FastAPI process)
  2. The `env.AGENT_API_KEY` field in your Windsurf MCP config (so the stdio server can attach the bearer header on every request)
- Generate one with:

  ```bash
  openssl rand -hex 32
  ```

- Rotate it whenever you want; just update both places and restart the API + your IDE.
- The UI does **not** use this key. The UI runs on localhost and writes are tagged `HUMAN` regardless.

## Zero-Config Setup

From a clean clone:

```bash
python3 bootstrap.py
```

This script will:

1. Create `.venv/` and install all backend + MCP dependencies
2. Generate a fresh `AGENT_API_KEY` (or accept one you paste in)
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

The SQLite database lives at `~/.taskable/taskable.db` by default — survives `git clean`, easy to back up, inspectable with any SQLite GUI.

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
AGENT_API_KEY=<same as .env> python mcp/mcp_server.py

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
| GET    | `/api/v1/projects`                                  |                               |
| POST   | `/api/v1/projects`                                  |                               |
| GET    | `/api/v1/projects/{id}`                             |                               |
| GET    | `/api/v1/projects/{id}/subprojects`                 |                               |
| POST   | `/api/v1/projects/{id}/subprojects`                 |                               |
| GET    | `/api/v1/subprojects/{id}`                          | Returns nested tickets.       |
| PATCH  | `/api/v1/subprojects/{id}`                          |                               |
| POST   | `/api/v1/subprojects/{id}/tickets`                  |                               |
| GET    | `/api/v1/tickets/{id}`                              | Nested comments + audit logs. |
| PATCH  | `/api/v1/tickets/{id}`                              | Writes audit entries.         |
| POST   | `/api/v1/tickets/{id}/mr`                           | Attach MR, emits `MR_LINKED`. |
| GET    | `/api/v1/tickets/{id}/comments`                     |                               |
| POST   | `/api/v1/tickets/{id}/comments`                     |                               |
| GET    | `/api/v1/events`                                    | SSE stream (heartbeat 15s).   |
| GET    | `/api/v1/agent/context/{id}`                        | **Bearer required.**          |

`GET /tickets/{id}` was added beyond the original spec so the client-side SSE-driven targeted refetch described in `docs/client_server.md` has a route to hit. Logged in `learnings.md`.

## Auth model

Per decision in `learnings.md`:

- **UI**: Runs on localhost, writes unauthenticated. Bearer header absent ⇒ audit entries tagged `HUMAN`.
- **MCP server**: Always injects `Authorization: Bearer ${AGENT_API_KEY}`. Routes under `/agent/*` **require** the bearer token.
- The API tags audit entries and SSE metadata with `HUMAN` vs `AGENT` based on the header.

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
