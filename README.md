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
                            ./data/taskable.db
```

- `api/` — FastAPI backend (SQLModel entities, routes, SSE broadcaster, pytest).
- `web/` — Vite + React + Tailwind UI with `useSSE` reactive refetch.
- `mcp/` — Python MCP stdio server exposing 5 agent tools.
- `docker/` — two-service docker-compose stack.

## Quick Start (local dev, no Docker)

### 1. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt

cp .env.example .env       # then edit AGENT_API_KEY

uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/docs` for the OpenAPI explorer.

### 2. Frontend

```bash
cd web
npm install
npm run dev   # http://127.0.0.1:5173
```

The Vite dev server proxies `/api/v1/*` to `http://localhost:8000`, so the UI works without CORS or env setup.

### 3. MCP Agent Server

```bash
pip install -r mcp/requirements.txt

# Smoke-run (stdio; use an MCP-aware client to interact)
AGENT_API_KEY=<same as .env> python mcp/mcp_server.py
```

Hook it into Windsurf by copying [`mcp/mcp.json.example`](./mcp/mcp.json.example) into your Windsurf MCP config (typically `~/.codeium/windsurf/mcp_config.json`) and substituting the absolute paths + key.

## Quick Start (Docker)

```bash
cp .env.example .env       # fill in AGENT_API_KEY
docker compose -f docker/docker-compose.yml up --build
```

- API: `http://localhost:8000`
- UI: `http://localhost:3000`
- SQLite persisted in the `sqlite_data` named volume.

The MCP server is **not** containerized — it runs on the host via stdio per `docs/deployment.md`, and points at `http://localhost:8000/api/v1` via the published API port.

## Testing

```bash
# Backend
pytest api/tests/ -v

# Frontend type-check + production build
cd web && npm run build
```

The pytest suite covers CRUD, state transitions, agent endpoints, and SSE broadcasting against an isolated in-memory SQLite.

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
