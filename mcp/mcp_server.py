"""Taskable MCP server.

Exposes the Taskable REST API to agentic IDEs (Windsurf, Claude Desktop, etc.)
over MCP stdio. The underlying REST API must be reachable on
``TASKABLE_API_URL`` (default ``http://localhost:8000/api/v1``).

Tools — kept in lock-step with ``docs/mcp.md``:
    1. ``read_subproject_context(subproject_id)``
    2. ``get_active_tasks(project_id)``
    3. ``update_ticket_status(ticket_id, status)``
    4. ``link_mr(ticket_id, url)``
    5. ``leave_comment(ticket_id, content)``

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
