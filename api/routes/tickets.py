"""Ticket detail, mutation, and MR linking endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.events import Event, get_broadcaster
from api.models.entities import AuditLog, Comment, Ticket
from api.models.enums import (
    ActorRole,
    AuditAction,
    SSEAction,
    TicketStatus,
)
from api.schemas import (
    AuditLogRead,
    CommentRead,
    MRLinkPayload,
    TicketDetail,
    TicketRead,
    TicketUpdate,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _get_or_404(session, ticket_id: int) -> Ticket:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


def _infer_actor(request: Request) -> ActorRole:
    """Detect whether the caller is the agent (bearer token) or the UI.

    We avoid a hard dependency on ``require_agent_key`` on mutation routes so
    the UI can write without auth on localhost; instead we *softly* tag the
    actor for the audit log based on the header.
    """
    from api.config import get_settings  # local import avoids cycle

    header = request.headers.get("authorization") or ""
    expected = f"Bearer {get_settings().agent_api_key}"
    return ActorRole.AGENT if header == expected else ActorRole.HUMAN


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: int, session: SessionDep) -> TicketDetail:
    ticket = _get_or_404(session, ticket_id)
    comments = list(
        session.exec(
            select(Comment)
            .where(Comment.ticket_id == ticket_id)
            .order_by(Comment.timestamp)
        ).all()
    )
    audit_logs = list(
        session.exec(
            select(AuditLog)
            .where(AuditLog.ticket_id == ticket_id)
            .order_by(AuditLog.timestamp)
        ).all()
    )
    return TicketDetail(
        id=ticket.id,  # type: ignore[arg-type]
        subproject_id=ticket.subproject_id,
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
        assignee=ticket.assignee,
        mr_link=ticket.mr_link,
        comments=[CommentRead.model_validate(c) for c in comments],
        audit_logs=[AuditLogRead.model_validate(a) for a in audit_logs],
    )


@router.patch("/{ticket_id}", response_model=TicketRead)
async def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    session: SessionDep,
    request: Request,
) -> Ticket:
    ticket = _get_or_404(session, ticket_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update.")

    actor = _infer_actor(request)
    audit_events: list[AuditAction] = []

    if "status" in updates:
        try:
            updates["status"] = TicketStatus(updates["status"])
        except ValueError as exc:  # pragma: no cover - pydantic catches this
            raise HTTPException(status_code=400, detail="Invalid status.") from exc
        if updates["status"] != ticket.status:
            audit_events.append(AuditAction.STATUS_UPDATE)

    if any(k in updates for k in ("title", "description")):
        original = {"title": ticket.title, "description": ticket.description}
        if any(updates.get(k) != original[k] for k in ("title", "description") if k in updates):
            audit_events.append(AuditAction.CONTENT_UPDATE)

    if "mr_link" in updates and updates["mr_link"] != ticket.mr_link and updates["mr_link"]:
        audit_events.append(AuditAction.MR_LINKED)

    for field_name, value in updates.items():
        setattr(ticket, field_name, value)

    session.add(ticket)
    for action in audit_events:
        session.add(AuditLog(ticket_id=ticket.id, action=action, actor=actor))
    session.commit()
    session.refresh(ticket)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.TICKET_UPDATED,
            entity="ticket",
            entity_id=ticket.id,  # type: ignore[arg-type]
            parent_id=ticket.subproject_id,
        )
    )
    return ticket


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_ticket(ticket_id: int, session: SessionDep) -> None:
    """Delete a ticket and cascade its comments and audit logs."""
    ticket = _get_or_404(session, ticket_id)
    subproject_id = ticket.subproject_id
    session.delete(ticket)
    session.commit()

    await get_broadcaster().publish(
        Event(
            action=SSEAction.TICKET_DELETED,
            entity="ticket",
            entity_id=ticket_id,
            parent_id=subproject_id,
        )
    )
    return None


@router.post(
    "/{ticket_id}/mr",
    response_model=TicketRead,
    status_code=status.HTTP_200_OK,
)
async def attach_mr_link(
    ticket_id: int,
    payload: MRLinkPayload,
    session: SessionDep,
    request: Request,
) -> Ticket:
    """Attach (or replace) the Git MR link on a ticket.

    Branch generation is intentionally out-of-scope for MVP. If a ``GITHUB_PAT``
    is provided later, this route can grow a branch-creation side-effect.
    """
    ticket = _get_or_404(session, ticket_id)
    actor = _infer_actor(request)

    ticket.mr_link = payload.url
    session.add(ticket)
    session.add(
        AuditLog(ticket_id=ticket.id, action=AuditAction.MR_LINKED, actor=actor)
    )
    session.commit()
    session.refresh(ticket)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.MR_LINKED,
            entity="ticket",
            entity_id=ticket.id,  # type: ignore[arg-type]
            parent_id=ticket.subproject_id,
        )
    )
    return ticket
