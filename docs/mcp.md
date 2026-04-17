# MCP Server Implementation Guide

## Objective
Build a Python-based Model Context Protocol (MCP) server exposing the workspace API to agentic IDEs via `stdio`.

## Dependencies
* `mcp` (Official Python SDK)
* `httpx` (Async HTTP client for REST calls)

## Configuration
* **API Target:** `http://localhost:8000/api/v1`
* **Transport:** Standard Input/Output (`stdio`)
* **Auth:** Inject `Authorization: Bearer {AGENT_API_KEY}` into all `httpx` headers.

## Tool Definitions
Expose the following capabilities using the `@server.tool()` decorator. Docstrings MUST be explicitly descriptive to ensure autonomous LLM comprehension.

1. **`read_subproject_context(subproject_id: int) -> str`**
   * **Action:** `GET /subprojects/{id}`
   * **Return:** Formatted string containing the `context_brief` and active tickets.
2. **`get_active_tasks(project_id: int) -> str`**
   * **Action:** `GET /projects/{id}/subprojects` (Filtered for active status).
3. **`update_ticket_status(ticket_id: int, status: str) -> str`**
   * **Action:** `PATCH /tickets/{id}`. Payload: `{"status": status, "assignee": "AGENT"}`.
4. **`link_mr(ticket_id: int, url: str) -> str`**
   * **Action:** `POST /tickets/{id}/mr`. Payload: `{"url": url}`.
5. **`leave_comment(ticket_id: int, content: str) -> str`**
   * **Action:** `POST /tickets/{id}/comments`. Payload: `{"author": "AGENT", "content": content}`.

## Execution Entrypoint
Initialize `mcp.server.Server("copilot-workspace")` and execute the async loop via `mcp.server.stdio.stdio_server()`.
