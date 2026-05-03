# Taskable MCP Server

A Model Context Protocol server that exposes the Taskable REST API to agentic
IDEs over `stdio`. The FastAPI backend must be running on the URL you supply
via `TASKABLE_API_URL` (default `http://localhost:8000/api/v1`).

## Install

```bash
# From the repo root (shares the backend's virtualenv to avoid duplication)
source .venv/bin/activate
pip install -r mcp/requirements.txt
```

## Run locally (smoke test)

```bash
AGENT_API_KEY=<same as .env> TASKABLE_API_URL=http://localhost:8000/api/v1 \
  python mcp/mcp_server.py
```

Stdio input/output is MCP protocol; use an MCP-aware client to interact.

## Windsurf configuration

Add the contents of `mcp.json.example` to your Windsurf MCP config
(typically `~/.codeium/windsurf/mcp_config.json`), then restart Windsurf. The
key **must** match the one in the FastAPI process's `.env`.

## Exposed Tools

| Tool                        | Action                                             |
| --------------------------- | -------------------------------------------------- |
| `get_all_projects`          | `GET /projects`                                    |
| `create_project`            | `POST /projects` (`name`, `description`)           |
| `create_subproject`         | `POST /projects/{id}/subprojects`                  |
| `create_ticket`             | `POST /subprojects/{id}/tickets`                   |
| `read_subproject_context`   | `GET /agent/context/{id}` — LLM-flat text brief    |
| `get_active_tasks`          | `GET /projects/{id}/subprojects`                   |
| `update_ticket_status`      | `PATCH /tickets/{id}` (`status`, `assignee=AGENT`) |
| `link_mr`                   | `POST /tickets/{id}/mr`                            |
| `leave_comment`             | `POST /tickets/{id}/comments` (`author=AGENT`)     |
| `delete_project`            | `DELETE /projects/{id}`                            |
| `delete_subproject`         | `DELETE /subprojects/{id}`                         |
| `delete_ticket`             | `DELETE /tickets/{id}`                             |
| `list_knowledge_nodes`      | `GET /agent/projects/{id}/knowledge`               |
| `read_knowledge_node`       | `GET /agent/knowledge/{id}`                        |
| `create_knowledge_node`     | `POST /projects/{id}/knowledge`                    |
| `update_knowledge_node`     | `PATCH /knowledge/{id}`                            |
| `delete_knowledge_node`     | `DELETE /knowledge/{id}`                           |

## Notes

- Transport is `stdio`; no network ports are opened by this process.
- Every HTTP call injects the static `Authorization: Bearer <AGENT_API_KEY>`
  header, satisfying the `/agent/*` route guard.
- Error payloads from the API bubble up verbatim so the LLM can self-correct.
