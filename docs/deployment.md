# Infrastructure & Deployment Blueprint

## Environment Configuration (`.env`)
* `AGENT_API_KEY`: Static bearer token for headless MCP authentication.
* `GITHUB_PAT`: Scoped GitHub Personal Access Token for MR linking.
* `VITE_API_URL`: Set to `http://localhost:8000/api/v1` for the Vite client.

## Docker Definitions

### Backend API (`Dockerfile.api`)
* **Base:** `python:3.11-slim`
* **Setup:** Install dependencies (`fastapi`, `sqlmodel`, `uvicorn`).
* **Execution:** Expose port `8000`. Run `uvicorn app.main:app --host 0.0.0.0`.

### Frontend Client (`Dockerfile.web`)
* **Stage 1 (Build):** `node:20-alpine`. Execute `npm install` and `npm run build`.
* **Stage 2 (Serve):** `nginx:alpine`. Copy `/dist` to `/usr/share/nginx/html`. Expose port `80`.

## Service Orchestration (`docker-compose.yml`)
* **Volumes:** Define `sqlite_data` to persist local state.
* **Networks:** Define `copilot_net` (bridge).
* **Services:**
  1. `api`: Build `Dockerfile.api`. Map ports `8000:8000`. Mount `sqlite_data:/app/data`.
  2. `web`: Build `Dockerfile.web`. Map ports `3000:80`. Depends on `api`.

## Windsurf Context (`mcp.json`)
Since Windsurf executes the MCP server locally via standard I/O, point the configuration directly to the local Python environment script (`mcp_server.py`) rather than dockerizing the MCP process itself. Inject `AGENT_API_KEY` into the `env` block.
