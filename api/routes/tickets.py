"""Ticket detail, mutation, and MR linking endpoints."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.events import Event, get_broadcaster
from api.models.entities import AuditLog, Comment, KnowledgeNode, Ticket, TicketDependency
from api.models.enums import (
    ActorRole,
    AuditAction,
    BlockedByCategory,
    SSEAction,
    TicketStatus,
)
from api.schemas import (
    AuditLogRead,
    ClaimPayload,
    CommentRead,
    HeartbeatPayload,
    MRLinkPayload,
    TicketDetail,
    TicketRead,
    TicketRef,
    TicketUpdate,
)
from api.utils.ticket_deps import get_depends_on, validate_and_set_deps

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _get_or_404(session, ticket_id: int) -> Ticket:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


def _infer_actor(request: Request) -> ActorRole:
    """Detect whether the caller is the agent (API key) or the UI (cookie).

    Uses the auth_method set by get_current_user: 'api_key' = AGENT,
    'cookie' = HUMAN. Falls back to HUMAN if unset.
    """
    if getattr(request.state, "auth_method", None) == "api_key":
        return ActorRole.AGENT
    return ActorRole.HUMAN


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
        blocked_by=ticket.blocked_by,
        blocked_reason=ticket.blocked_reason,
        source_refs=ticket.source_refs or [],
        depends_on=get_depends_on(session, ticket_id),
        claimed_by=ticket.claimed_by,
        claimed_at=ticket.claimed_at,
        lease_expires_at=ticket.lease_expires_at,
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
        new_status = updates["status"]
        if new_status == TicketStatus.BLOCKED and not updates.get("blocked_by") and not ticket.blocked_by:
            raise HTTPException(
                status_code=422,
                detail="blocked_by is required when setting status to BLOCKED.",
            )
        if new_status != TicketStatus.BLOCKED:
            updates["blocked_by"] = None
            updates["blocked_reason"] = None
        if new_status != ticket.status:
            audit_events.append(AuditAction.STATUS_UPDATE)

    if any(k in updates for k in ("title", "description")):
        original = {"title": ticket.title, "description": ticket.description}
        if any(updates.get(k) != original[k] for k in ("title", "description") if k in updates):
            audit_events.append(AuditAction.CONTENT_UPDATE)

    if "mr_link" in updates and updates["mr_link"] != ticket.mr_link and updates["mr_link"]:
        audit_events.append(AuditAction.MR_LINKED)

    if "depends_on" in updates:
        validate_and_set_deps(
            session, ticket.id, ticket.subproject_id, updates["depends_on"]  # type: ignore[arg-type]
        )
        # Remove from updates so the setattr loop doesn't try to set it on the model.
        del updates["depends_on"]

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


@router.get("/knowledge/{node_id}/tickets", response_model=list[TicketRef])
def get_tickets_for_node(node_id: int, session: SessionDep) -> list[Ticket]:
    """Return all tickets whose source_refs include this knowledge node."""
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found.")
    ref_str = f"node:{node_id}"
    tickets = list(
        session.exec(select(Ticket)).all()
    )
    return [t for t in tickets if ref_str in (t.source_refs or [])]


# ---- Claim / heartbeat / requeue -----------------------------------------


_DEFAULT_LEASE_SECONDS = 600  # 10 minutes


@router.post("/{ticket_id}/claim", response_model=TicketRead)
async def claim_ticket(
    ticket_id: int,
    payload: ClaimPayload,
    session: SessionDep,
    request: Request,
) -> TicketRead:
    """Atomically transition a TODO ticket to IN_PROGRESS and set worker identity.

    Returns 200 on success, 409 if already claimed or not ready (unmet deps).
    """
    from api.utils.time import utcnow
    from api.utils.ticket_deps import is_ticket_ready

    ticket = _get_or_404(session, ticket_id)

    if ticket.status != TicketStatus.TODO or not is_ticket_ready(session, ticket):
        raise HTTPException(
            status_code=409,
            detail="Ticket is not available for claiming (not TODO or dependencies unmet).",
        )

    now = utcnow()
    ticket.status = TicketStatus.IN_PROGRESS
    ticket.claimed_by = payload.worker_id
    ticket.claimed_at = now
    ticket.lease_expires_at = now.replace(microsecond=0) + timedelta(seconds=_DEFAULT_LEASE_SECONDS)

    actor = _infer_actor(request)
    session.add(ticket)
    session.add(
        AuditLog(
            ticket_id=ticket.id,
            action=AuditAction.TICKET_CLAIMED,
            actor=actor,
        )
    )
    session.commit()
    session.refresh(ticket)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.TICKET_CLAIMED,
            entity="ticket",
            entity_id=ticket.id,  # type: ignore[arg-type]
            parent_id=ticket.subproject_id,
        )
    )
    return TicketRead(
        id=ticket.id,  # type: ignore[arg-type]
        subproject_id=ticket.subproject_id,
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
        assignee=ticket.assignee,
        mr_link=ticket.mr_link,
        blocked_by=ticket.blocked_by,
        blocked_reason=ticket.blocked_reason,
        source_refs=ticket.source_refs or [],
        depends_on=get_depends_on(session, ticket_id),
        claimed_by=ticket.claimed_by,
        claimed_at=ticket.claimed_at,
        lease_expires_at=ticket.lease_expires_at,
    )


@router.post("/{ticket_id}/heartbeat", response_model=TicketRead)
async def heartbeat_ticket(
    ticket_id: int,
    payload: HeartbeatPayload,
    session: SessionDep,
) -> TicketRead:
    """Extend the lease on a claimed ticket.

    The ``worker_id`` must match ``claimed_by``. Returns 200 with the updated
    ticket, 409 if the worker doesn't own the ticket.
    """
    from api.utils.time import utcnow

    ticket = _get_or_404(session, ticket_id)

    if ticket.claimed_by != payload.worker_id:
        raise HTTPException(
            status_code=409,
            detail=f"Worker '{payload.worker_id}' does not own ticket {ticket_id}.",
        )

    now = utcnow()
    ticket.lease_expires_at = now.replace(microsecond=0) + timedelta(seconds=payload.extend_seconds)

    session.add(ticket)
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
    return TicketRead(
        id=ticket.id,  # type: ignore[arg-type]
        subproject_id=ticket.subproject_id,
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
        assignee=ticket.assignee,
        mr_link=ticket.mr_link,
        blocked_by=ticket.blocked_by,
        blocked_reason=ticket.blocked_reason,
        source_refs=ticket.source_refs or [],
        depends_on=get_depends_on(session, ticket_id),
        claimed_by=ticket.claimed_by,
        claimed_at=ticket.claimed_at,
        lease_expires_at=ticket.lease_expires_at,
    )


@router.post("/subprojects/{subproject_id}/requeue-expired", response_model=list[TicketRead])
async def requeue_expired(
    subproject_id: int,
    session: SessionDep,
) -> list[TicketRead]:
    """Revert IN_PROGRESS tickets with expired leases back to TODO.

    Clears claim fields and writes a TICKET_REQUEUED audit log entry for each.
    """
    from api.utils.time import utcnow

    now = utcnow()
    tickets = list(
        session.exec(
            select(Ticket)
            .where(Ticket.subproject_id == subproject_id)
            .where(Ticket.status == TicketStatus.IN_PROGRESS)
            .where(Ticket.lease_expires_at.is_not(None))  # type: ignore[union-attr]
            .where(Ticket.lease_expires_at < now)  # type: ignore[operator]
        ).all()
    )
    result: list[TicketRead] = []
    for ticket in tickets:
        ticket.status = TicketStatus.TODO
        ticket.claimed_by = None
        ticket.claimed_at = None
        ticket.lease_expires_at = None
        session.add(ticket)
        session.add(
            AuditLog(
                ticket_id=ticket.id,
                action=AuditAction.TICKET_REQUEUED,
                actor=ActorRole.AGENT,
            )
        )
        result.append(
            TicketRead(
                id=ticket.id,  # type: ignore[arg-type]
                subproject_id=ticket.subproject_id,
                title=ticket.title,
                description=ticket.description,
                status=ticket.status,
                assignee=ticket.assignee,
                mr_link=ticket.mr_link,
                blocked_by=ticket.blocked_by,
                blocked_reason=ticket.blocked_reason,
                source_refs=ticket.source_refs or [],
                depends_on=get_depends_on(session, ticket.id),  # type: ignore[arg-type]
                claimed_by=ticket.claimed_by,
                claimed_at=ticket.claimed_at,
                lease_expires_at=ticket.lease_expires_at,
            )
        )
    session.commit()

    for ticket in tickets:
        await get_broadcaster().publish(
            Event(
                action=SSEAction.TICKET_REQUEUED,
                entity="ticket",
                entity_id=ticket.id,  # type: ignore[arg-type]
                parent_id=subproject_id,
            )
        )
    return result
