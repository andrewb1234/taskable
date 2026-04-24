"""Agent-specific endpoints.

These routes require the static ``AGENT_API_KEY`` bearer token because they
produce LLM-optimized payloads that we only want exposed to the MCP server.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlmodel import select

from api.dependencies import SessionDep, require_agent_key
from api.models.entities import KnowledgeNode, Project, Subproject, Ticket

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


def _format_knowledge_tree(project: Project, nodes: list[KnowledgeNode]) -> str:
    """Render the knowledge tree as a compact LLM-friendly outline.

    Each node is a single indented line tagged with ``[TYPE #id]``. The
    body text is intentionally omitted: the agent drills down via
    ``GET /agent/knowledge/{id}`` — that is the whole point of leaving
    breadcrumbs instead of dumping raw content into every call.
    """
    children: dict[int | None, list[KnowledgeNode]] = {}
    for node in nodes:
        children.setdefault(node.parent_id, []).append(node)
    for sibling_list in children.values():
        sibling_list.sort(key=lambda n: (n.created_at, n.id or 0))

    lines: list[str] = [
        f"# Knowledge tree for project #{project.id}: {project.name}",
    ]
    if not nodes:
        lines.append("(empty — no knowledge nodes ingested yet)")
        return "\n".join(lines)

    def walk(parent_id: int | None, depth: int) -> None:
        for node in children.get(parent_id, []):
            indent = "  " * depth
            refs = ""
            if node.source_refs:
                preview = ", ".join(node.source_refs[:3])
                if len(node.source_refs) > 3:
                    preview += f", …(+{len(node.source_refs) - 3})"
                refs = f"  [refs: {preview}]"
            lines.append(
                f"{indent}- [{node.node_type.value} #{node.id}] {node.title}{refs}"
            )
            walk(node.id, depth + 1)

    walk(None, 0)
    lines.append("")
    lines.append(
        "To read a node's full content call GET /agent/knowledge/{id} "
        "(or the read_knowledge_node MCP tool)."
    )
    return "\n".join(lines)


@router.get(
    "/projects/{project_id}/knowledge",
    response_class=PlainTextResponse,
)
def get_agent_knowledge_map(project_id: int, session: SessionDep) -> str:
    """Compact plain-text outline of a project's knowledge tree for agents."""
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    nodes = list(
        session.exec(
            select(KnowledgeNode)
            .where(KnowledgeNode.project_id == project_id)
            .order_by(KnowledgeNode.created_at, KnowledgeNode.id)
        ).all()
    )
    return _format_knowledge_tree(project, nodes)


@router.get(
    "/knowledge/{node_id}",
    response_class=PlainTextResponse,
)
def get_agent_knowledge_node(node_id: int, session: SessionDep) -> str:
    """Return a single knowledge node flattened for the agent's context."""
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found.")

    lines: list[str] = [
        f"# [{node.node_type.value} #{node.id}] {node.title}",
        f"project_id={node.project_id}"
        + (f"  parent_id={node.parent_id}" if node.parent_id else ""),
        f"created_by={node.created_by.value}  created_at={node.created_at.isoformat()}",
    ]
    if node.source_refs:
        lines.append("")
        lines.append("## Source references")
        for ref in node.source_refs:
            lines.append(f"- {ref}")
    lines.append("")
    lines.append("## Content")
    lines.append(node.content.strip() or "(empty)")
    return "\n".join(lines)
