# MCP Server — Current State

Python-based Model Context Protocol (MCP) server that exposes the Taskable REST
API to agentic IDEs (Windsurf, Claude Desktop, etc.) over a `stdio` transport.

> **Source of truth:** `mcp/mcp_server.py`. Every tool below is registered in
> the `TOOLS` list and dispatched from `TOOL_DISPATCH`.

## Dependencies
* `mcp >=1.1` (Official Python SDK)
* `httpx` (Async HTTP client for REST calls)
* `python-dotenv` (reads `AGENT_API_KEY` / `TASKABLE_API_URL` from the repo's `.env`)

See `mcp/pyproject.toml` for the packaging manifest. Install via
`pipx install ./mcp`, `uv tool install ./mcp`, or `pip install -e ./mcp` to
get the `taskable-mcp` console script.

## Configuration
* **API Target:** `TASKABLE_API_URL` (default `http://localhost:8000/api/v1`).
  Trailing slashes are stripped at load time.
* **Transport:** Standard Input/Output (`stdio`).
* **Auth:** Every request sends `Authorization: Bearer {AGENT_API_KEY}`. The
  same value must be set in the FastAPI server's environment.

## Tool Catalogue

All tools return a plain-text `TextContent` frame. Error responses begin with
`ERROR:` so callers can detect failure without parsing JSON.

### Read tools

1. **`get_all_projects() -> str`**
   * **Action:** `GET /api/v1/projects`
   * **Return:** Markdown list of projects with their IDs and descriptions.
     Returns a hint to call `create_project` if no projects exist.

2. **`get_active_tasks(project_id: int) -> str`**
   * **Action:** `GET /api/v1/projects/{project_id}/subprojects`
   * **Return:** Human-readable list of subprojects under the project,
     flagging the `ACTIVE` one(s). Useful before `read_subproject_context`.

3. **`read_subproject_context(subproject_id: int) -> str`**
   * **Action:** `GET /api/v1/agent/context/{subproject_id}`
   * **Return:** Full flattened LLM-optimized text including the
     `context_brief` and every non-DONE ticket (status / assignee / MR link).
     **Call this first** to orient before touching any tickets.

### Create tools

4. **`create_project(name: str, description: str) -> str`**
   * **Action:** `POST /api/v1/projects`
   * **Payload:** `{"name": name, "description": description}`
   * **Return:** Confirmation with the new project's ID, formatted so
     subsequent `create_subproject` calls can extract it.

5. **`create_subproject(project_id: int, name: str, context_brief: str) -> str`**
   * **Action:** `POST /api/v1/projects/{project_id}/subprojects`
   * **Payload:** `{"name": name, "context_brief": context_brief}`
   * **Return:** Confirmation with the new subproject's ID and parent project.
     Returns an explicit `ERROR` if the project does not exist.

6. **`create_ticket(subproject_id: int, title: str, description: str, assignee: str) -> str`**
   * **Action:** `POST /api/v1/subprojects/{subproject_id}/tickets`
   * **Payload:** `{"title": title, "description": description, "assignee": assignee}`
   * **Constraint:** `assignee` must be `HUMAN`, `AGENT`, or `UNASSIGNED`
     (case-insensitive at tool entry; normalized to uppercase before POST).
     Enforced both by the tool's `inputSchema.enum` AND by an in-handler guard.
   * **Note:** Tickets always start in `TODO`. Use `update_ticket_status` to
     move them afterwards.

### Mutate tools

7. **`update_ticket_status(ticket_id: int, status: str) -> str`**
   * **Action:** `PATCH /api/v1/tickets/{ticket_id}`
   * **Payload:** `{"status": status, "assignee": "AGENT"}` (the agent always
     claims the ticket on status change — matches PRD expectations).
   * **Constraint:** `status` must be one of `TODO`, `IN_PROGRESS`, `BLOCKED`,
     `REVIEW`, `DONE`.

8. **`link_mr(ticket_id: int, url: str) -> str`**
   * **Action:** `POST /api/v1/tickets/{ticket_id}/mr`
   * **Payload:** `{"url": url}`
   * **Side effects:** Writes an `AuditLog` entry with `action=MR_LINKED`;
     broadcasts an SSE event so the UI refreshes live.

9. **`leave_comment(ticket_id: int, content: str) -> str`**
   * **Action:** `POST /api/v1/tickets/{ticket_id}/comments`
   * **Payload:** `{"author": "AGENT", "content": content}`

## Execution Entrypoint
`Server("copilot-workspace")` is run via `mcp.server.stdio.stdio_server()`
inside `main() -> asyncio.run(amain())`. The installed console script
`taskable-mcp` calls `main()` directly.

## IDE / Client Configuration
See `mcp/mcp.json.example` for a drop-in Windsurf / Claude Desktop block with
both the `taskable-mcp`-on-`$PATH` form and the venv-relative fallback.

## Testing
* `api/tests/test_mcp_simulator.py` boots a real uvicorn + the MCP stdio
  server as subprocesses and drives the full JSON-RPC handshake. Three
  scenarios cover: (a) the read/mutate flow, (b) invalid-status rejection,
  and (c) the create-project → create-subproject → create-ticket chain with
  DB verification. Run with `.venv/bin/pytest api/tests/test_mcp_simulator.py`.
