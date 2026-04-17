"""Agent-specific endpoints.

These routes require the static ``AGENT_API_KEY`` bearer token because they
produce LLM-optimized payloads that we only want exposed to the MCP server.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlmodel import select

from api.dependencies import SessionDep, require_agent_key
from api.models.entities import Subproject, Ticket

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(require_agent_key)])


def _format_context(subproject: Subproject, tickets: list[Ticket]) -> str:
    """Flatten a subproject and its tickets into LLM-friendly plain text."""

    lines: list[str] = []
    lines.append(f"# Subproject: {subproject.name} (id={subproject.id})")
    lines.append(f"Status: {subproject.status.value}")
    lines.append("")
    lines.append("## Context Brief")
    lines.append(subproject.context_brief.strip() or "(no brief provided)")
    lines.append("")
    lines.append("## Active Tickets")
    if not tickets:
        lines.append("(none)")
    else:
        for ticket in tickets:
            mr = f" [MR: {ticket.mr_link}]" if ticket.mr_link else ""
            desc = (ticket.description or "").strip().replace("\n", " ")
            if len(desc) > 160:
                desc = desc[:157] + "..."
            lines.append(
                f"- #{ticket.id} [{ticket.status.value}/{ticket.assignee.value}] "
                f"{ticket.title}{mr}"
            )
            if desc:
                lines.append(f"    {desc}")
    return "\n".join(lines)


@router.get("/context/{subproject_id}", response_class=PlainTextResponse)
def get_agent_context(subproject_id: int, session: SessionDep) -> str:
    subproject = session.get(Subproject, subproject_id)
    if subproject is None:
        raise HTTPException(status_code=404, detail="Subproject not found.")
    tickets = list(
        session.exec(
            select(Ticket)
            .where(Ticket.subproject_id == subproject_id)
            .order_by(Ticket.id)
        ).all()
    )
    return _format_context(subproject, tickets)
