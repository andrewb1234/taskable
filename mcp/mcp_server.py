"""Taskable MCP server.

Exposes the Taskable REST API to agentic IDEs (Windsurf, Claude Desktop, etc.)
over MCP stdio. The underlying REST API must be reachable on
``TASKABLE_API_URL`` (default ``http://localhost:8000/api/v1``).

Tools — kept in lock-step with ``docs/mcp.md``:
    Read:
        1. ``get_all_projects()``
        2. ``get_active_tasks(project_id)``
        3. ``read_subproject_context(subproject_id)``
    Create:
        4. ``create_project(name, description)``
        5. ``create_subproject(project_id, name, context_brief)``
        6. ``create_ticket(subproject_id, title, description, assignee)``
    Mutate:
        7. ``update_ticket_status(ticket_id, status)``
        8. ``link_mr(ticket_id, url)``
        9. ``leave_comment(ticket_id, content)``

Docstrings are intentionally verbose so LLM clients have precise schemas and
behavioral expectations without having to re-read the spec.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

load_dotenv()
load_dotenv("../.env")

API_URL = os.getenv("TASKABLE_API_URL", "http://localhost:8000/api/v1").rstrip("/")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")

VALID_TICKET_STATUSES = {"TODO", "IN_PROGRESS", "BLOCKED", "REVIEW", "DONE"}
VALID_TICKET_ASSIGNEES = {"HUMAN", "AGENT", "UNASSIGNED"}

server: Server = Server("copilot-workspace")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {AGENT_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain;q=0.9, */*;q=0.5",
    }


def _wrap(text: str) -> list[TextContent]:
    """Every MCP tool return value is a list of content parts."""
    return [TextContent(type="text", text=text)]


async def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(timeout=15.0) as client:
        return await client.request(
            method, f"{API_URL}{path}", headers=_headers(), **kwargs
        )


# ---- Tool implementations -------------------------------------------------


async def get_all_projects() -> str:
    """List every project in the workspace with their IDs.

    Calls ``GET /api/v1/projects``. Intended as the first tool an agent uses
    to orient itself before drilling into a specific project's subprojects.
    """
    response = await _request("GET", "/projects")
    if response.status_code != 200:
        return (
            f"ERROR: list projects failed "
            f"(status={response.status_code}): {response.text}"
        )
    projects = response.json()
    if not projects:
        return "No projects exist yet. Use create_project to create one."

    lines = ["# Projects"]
    for project in projects:
        desc = (project.get("description") or "").strip()
        suffix = f" — {desc}" if desc else ""
        lines.append(f"- id={project['id']} | {project['name']}{suffix}")
    return "\n".join(lines)


async def create_project(name: str, description: str) -> str:
    """Create a new top-level project.

    Calls ``POST /api/v1/projects`` with ``{"name": name, "description":
    description}``. Returns the new project's ID so subsequent
    ``create_subproject`` calls can wire to it.
    """
    response = await _request(
        "POST",
        "/projects",
        json={"name": name, "description": description},
    )
    if response.status_code != 201:
        return (
            f"ERROR: create project failed "
            f"(status={response.status_code}): {response.text}"
        )
    project = response.json()
    return (
        f"Created project #{project['id']}: {project['name']}. "
        f"Use this id when calling create_subproject."
    )


async def create_subproject(
    project_id: int, name: str, context_brief: str
) -> str:
    """Create a subproject (sprint-like unit) under an existing project.

    Calls ``POST /api/v1/projects/{project_id}/subprojects`` with
    ``{"name": name, "context_brief": context_brief}``. The context brief is
    the primary thing an agent later reads via ``read_subproject_context``, so
    it should be rich and goal-oriented.
    """
    response = await _request(
        "POST",
        f"/projects/{int(project_id)}/subprojects",
        json={"name": name, "context_brief": context_brief},
    )
    if response.status_code == 404:
        return f"ERROR: project {project_id} does not exist."
    if response.status_code != 201:
        return (
            f"ERROR: create subproject failed "
            f"(status={response.status_code}): {response.text}"
        )
    subproject = response.json()
    return (
        f"Created subproject #{subproject['id']} "
        f"(project={subproject['project_id']}): {subproject['name']}."
    )


async def create_ticket(
    subproject_id: int,
    title: str,
    description: str,
    assignee: str,
) -> str:
    """Create a new ticket inside a subproject.

    Calls ``POST /api/v1/subprojects/{subproject_id}/tickets`` with
    ``{"title": title, "description": description, "assignee": assignee}``.
    ``assignee`` must be one of HUMAN, AGENT, or UNASSIGNED (case-insensitive
    on the way in; normalized before the request). New tickets always start
    in TODO status — use ``update_ticket_status`` afterwards to move them.
    """
    assignee_upper = assignee.upper()
    if assignee_upper not in VALID_TICKET_ASSIGNEES:
        return (
            f"ERROR: invalid assignee '{assignee}'. "
            f"Valid values: {sorted(VALID_TICKET_ASSIGNEES)}."
        )

    response = await _request(
        "POST",
        f"/subprojects/{int(subproject_id)}/tickets",
        json={
            "title": title,
            "description": description,
            "assignee": assignee_upper,
        },
    )
    if response.status_code == 404:
        return f"ERROR: subproject {subproject_id} does not exist."
    if response.status_code != 201:
        return (
            f"ERROR: create ticket failed "
            f"(status={response.status_code}): {response.text}"
        )
    ticket = response.json()
    return (
        f"Created ticket #{ticket['id']} [{ticket['status']}/{ticket['assignee']}] "
        f"{ticket['title']} (subproject={ticket['subproject_id']})."
    )


async def read_subproject_context(subproject_id: int) -> str:
    """Return the full flattened context for a subproject (LLM-optimized).

    Calls ``GET /api/v1/agent/context/{subproject_id}`` and returns the raw
    plain-text body, which already contains the context brief and the list of
    active tickets with statuses, assignees, and MR links.
    """
    response = await _request("GET", f"/agent/context/{int(subproject_id)}")
    if response.status_code == 200:
        return response.text
    return (
        f"ERROR: agent context request failed "
        f"(status={response.status_code}): {response.text}"
    )


async def get_active_tasks(project_id: int) -> str:
    """List subprojects inside a project, flagging which are ACTIVE.

    Intended for an agent that needs to decide which subproject to work on
    before calling ``read_subproject_context``.
    """
    response = await _request("GET", f"/projects/{int(project_id)}/subprojects")
    if response.status_code != 200:
        return (
            f"ERROR: list subprojects failed "
            f"(status={response.status_code}): {response.text}"
        )
    subprojects = response.json()
    if not subprojects:
        return f"No subprojects exist under project {project_id}."

    lines = [f"# Subprojects of project {project_id}"]
    for sp in subprojects:
        marker = "* ACTIVE" if sp["status"] == "ACTIVE" else f"  {sp['status']}"
        lines.append(
            f"{marker} — id={sp['id']} | {sp['name']}\n    {sp.get('context_brief', '').strip()}"
        )
    return "\n".join(lines)


async def update_ticket_status(ticket_id: int, status: str) -> str:
    """Transition a ticket to a new status and claim it for the agent.

    Payload: ``{"status": status, "assignee": "AGENT"}``. The ``status`` must
    be one of TODO, IN_PROGRESS, BLOCKED, REVIEW, DONE (case-sensitive).
    """
    status_upper = status.upper()
    if status_upper not in VALID_TICKET_STATUSES:
        return (
            f"ERROR: invalid status '{status}'. "
            f"Valid values: {sorted(VALID_TICKET_STATUSES)}."
        )

    response = await _request(
        "PATCH",
        f"/tickets/{int(ticket_id)}",
        json={"status": status_upper, "assignee": "AGENT"},
    )
    if response.status_code != 200:
        return (
            f"ERROR: patch ticket {ticket_id} failed "
            f"(status={response.status_code}): {response.text}"
        )
    ticket = response.json()
    return (
        f"Updated ticket #{ticket['id']} → status={ticket['status']}, "
        f"assignee={ticket['assignee']}."
    )


async def link_mr(ticket_id: int, url: str) -> str:
    """Attach a Merge Request URL to a ticket.

    Writes an ``MR_LINKED`` entry to the AuditLog and broadcasts the
    corresponding SSE event, which causes the UI to refresh automatically.
    """
    response = await _request(
        "POST", f"/tickets/{int(ticket_id)}/mr", json={"url": url}
    )
    if response.status_code != 200:
        return (
            f"ERROR: MR link failed "
            f"(status={response.status_code}): {response.text}"
        )
    ticket = response.json()
    return f"Linked MR on ticket #{ticket['id']}: {ticket['mr_link']}"


async def leave_comment(ticket_id: int, content: str) -> str:
    """Append an AGENT-authored comment on a ticket's thread."""
    response = await _request(
        "POST",
        f"/tickets/{int(ticket_id)}/comments",
        json={"author": "AGENT", "content": content},
    )
    if response.status_code != 201:
        return (
            f"ERROR: comment create failed "
            f"(status={response.status_code}): {response.text}"
        )
    comment = response.json()
    return f"Posted comment #{comment['id']} on ticket #{comment['ticket_id']}."


# ---- MCP wiring -----------------------------------------------------------


TOOLS: list[Tool] = [
    Tool(
        name="get_all_projects",
        description=(
            "List every project in the workspace (id + name + description). "
            "Call this first when you have no project context."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="create_project",
        description=(
            "Create a new top-level project. Returns the new project's ID "
            "so you can create subprojects underneath it."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Short, human-readable project name.",
                    "minLength": 1,
                },
                "description": {
                    "type": "string",
                    "description": "Longer prose explaining the project's purpose.",
                },
            },
            "required": ["name", "description"],
        },
    ),
    Tool(
        name="create_subproject",
        description=(
            "Create a sprint-like subproject under an existing project. "
            "The context_brief will be surfaced verbatim to future agents "
            "via read_subproject_context, so make it rich and goal-oriented."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "ID of the parent project (from get_all_projects).",
                },
                "name": {"type": "string", "minLength": 1},
                "context_brief": {
                    "type": "string",
                    "description": "Multi-sentence brief describing goals, scope, and constraints.",
                },
            },
            "required": ["project_id", "name", "context_brief"],
        },
    ),
    Tool(
        name="create_ticket",
        description=(
            "Create a new ticket inside a subproject. Tickets always start "
            "in TODO status; use update_ticket_status to move them. "
            "Assignee must be HUMAN, AGENT, or UNASSIGNED."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "subproject_id": {
                    "type": "integer",
                    "description": "ID of the parent subproject.",
                },
                "title": {"type": "string", "minLength": 1},
                "description": {
                    "type": "string",
                    "description": "Task details, acceptance criteria, links.",
                },
                "assignee": {
                    "type": "string",
                    "enum": sorted(VALID_TICKET_ASSIGNEES),
                    "description": "Who owns the ticket on creation.",
                },
            },
            "required": [
                "subproject_id",
                "title",
                "description",
                "assignee",
            ],
        },
    ),
    Tool(
        name="read_subproject_context",
        description=(
            "Return the full flattened context for a subproject, including "
            "the context brief and the current ticket list (status, assignee, "
            "MR links). Call this first so you understand the overarching goal "
            "before touching any tickets."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "subproject_id": {
                    "type": "integer",
                    "description": "ID of the subproject to read.",
                }
            },
            "required": ["subproject_id"],
        },
    ),
    Tool(
        name="get_active_tasks",
        description=(
            "List the subprojects that belong to a project, annotating the "
            "ACTIVE one(s). Use this to choose which subproject to orient "
            "yourself in via read_subproject_context."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "ID of the parent project.",
                }
            },
            "required": ["project_id"],
        },
    ),
    Tool(
        name="update_ticket_status",
        description=(
            "Move a ticket to a new status and claim it for the agent. "
            "`status` must be one of TODO, IN_PROGRESS, BLOCKED, REVIEW, DONE."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer"},
                "status": {
                    "type": "string",
                    "enum": sorted(VALID_TICKET_STATUSES),
                },
            },
            "required": ["ticket_id", "status"],
        },
    ),
    Tool(
        name="link_mr",
        description=(
            "Attach a Merge Request / Pull Request URL to a ticket. "
            "The backend records this in the audit log and notifies the UI."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer"},
                "url": {
                    "type": "string",
                    "description": "Full URL of the MR, e.g. "
                    "https://github.com/org/repo/pull/123",
                },
            },
            "required": ["ticket_id", "url"],
        },
    ),
    Tool(
        name="leave_comment",
        description=(
            "Post an agent-authored comment on a ticket so the human can see "
            "what the agent is doing and why."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer"},
                "content": {"type": "string"},
            },
            "required": ["ticket_id", "content"],
        },
    ),
]


TOOL_DISPATCH = {
    "get_all_projects": get_all_projects,
    "create_project": create_project,
    "create_subproject": create_subproject,
    "create_ticket": create_ticket,
    "read_subproject_context": read_subproject_context,
    "get_active_tasks": get_active_tasks,
    "update_ticket_status": update_ticket_status,
    "link_mr": link_mr,
    "leave_comment": leave_comment,
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[TextContent]:
    handler = TOOL_DISPATCH.get(name)
    if handler is None:
        return _wrap(f"ERROR: unknown tool '{name}'")
    try:
        result = await handler(**(arguments or {}))
    except TypeError as exc:
        return _wrap(f"ERROR: bad arguments for {name}: {exc}")
    except httpx.RequestError as exc:
        return _wrap(
            f"ERROR: API request to {API_URL} failed ({exc.__class__.__name__}): {exc}"
        )
    return _wrap(result)


async def amain() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
