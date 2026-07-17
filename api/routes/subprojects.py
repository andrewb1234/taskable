"""Subproject detail + update + ticket-creation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.events import Event, get_broadcaster
from api.models.entities import Subproject, Ticket
from api.models.enums import SSEAction, TicketStatus
from api.schemas import (
    SubprojectDetail,
    SubprojectRead,
    SubprojectUpdate,
    TicketCreate,
    TicketRead,
)
from api.utils.ticket_deps import get_depends_on_map, is_ticket_ready

router = APIRouter(prefix="/subprojects", tags=["subprojects"])


def _get_or_404(session, subproject_id: int) -> Subproject:
    subproject = session.get(Subproject, subproject_id)
    if subproject is None:
        raise HTTPException(status_code=404, detail="Subproject not found.")
    return subproject


@router.get("/{subproject_id}", response_model=SubprojectDetail)
def get_subproject(
    subproject_id: int,
    session: SessionDep,
    ready: bool = Query(default=False),
) -> SubprojectDetail:
    subproject = _get_or_404(session, subproject_id)
    tickets = list(
        session.exec(
            select(Ticket)
            .where(Ticket.subproject_id == subproject_id)
            .order_by(Ticket.id)
        ).all()
    )
    if ready:
        tickets = [t for t in tickets if is_ticket_ready(session, t)]
    dep_map = get_depends_on_map(session, [t.id for t in tickets if t.id])  # type: ignore[arg-type]
    ticket_reads = []
    for t in tickets:
        tr = TicketRead.model_validate(t)
        tr.depends_on = dep_map.get(t.id, [])  # type: ignore[arg-type]
        ticket_reads.append(tr)
    return SubprojectDetail(
        id=subproject.id,  # type: ignore[arg-type]
        project_id=subproject.project_id,
        name=subproject.name,
        context_brief=subproject.context_brief,
        status=subproject.status,
        tickets=ticket_reads,
    )


@router.patch("/{subproject_id}", response_model=SubprojectRead)
async def update_subproject(
    subproject_id: int,
    payload: SubprojectUpdate,
    session: SessionDep,
) -> Subproject:
    subproject = _get_or_404(session, subproject_id)

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update.")

    for field_name, value in updates.items():
        setattr(subproject, field_name, value)

    session.add(subproject)
    session.commit()
    session.refresh(subproject)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.SUBPROJECT_UPDATED,
            entity="subproject",
            entity_id=subproject.id,  # type: ignore[arg-type]
            parent_id=subproject.project_id,
        )
    )
    return subproject


@router.delete(
    "/{subproject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_subproject(subproject_id: int, session: SessionDep) -> None:
    """Delete a subproject and cascade its tickets, comments, and audit logs."""
    subproject = _get_or_404(session, subproject_id)
    project_id = subproject.project_id
    session.delete(subproject)
    session.commit()

    await get_broadcaster().publish(
        Event(
            action=SSEAction.SUBPROJECT_DELETED,
            entity="subproject",
            entity_id=subproject_id,
            parent_id=project_id,
        )
    )
    return None


@router.post(
    "/{subproject_id}/tickets",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    subproject_id: int,
    payload: TicketCreate,
    session: SessionDep,
) -> TicketRead:
    _get_or_404(session, subproject_id)

    ticket = Ticket(
        subproject_id=subproject_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        assignee=payload.assignee,
        source_refs=list(payload.source_refs),
    )
    session.add(ticket)
    session.flush()  # get the id without committing yet

    if payload.depends_on:
        from api.utils.ticket_deps import validate_and_set_deps

        validate_and_set_deps(session, ticket.id, subproject_id, payload.depends_on)  # type: ignore[arg-type]

    session.commit()
    session.refresh(ticket)

    from api.utils.ticket_deps import get_depends_on

    deps = get_depends_on(session, ticket.id)  # type: ignore[arg-type]

    await get_broadcaster().publish(
        Event(
            action=SSEAction.TICKET_CREATED,
            entity="ticket",
            entity_id=ticket.id,  # type: ignore[arg-type]
            parent_id=subproject_id,
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
        depends_on=deps,
        claimed_by=ticket.claimed_by,
        claimed_at=ticket.claimed_at,
        lease_expires_at=ticket.lease_expires_at,
    )
