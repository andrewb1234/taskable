"""Subproject detail + update + ticket-creation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.events import Event, get_broadcaster
from api.models.entities import Subproject, Ticket
from api.models.enums import SSEAction
from api.schemas import (
    SubprojectDetail,
    SubprojectRead,
    SubprojectUpdate,
    TicketCreate,
    TicketRead,
)

router = APIRouter(prefix="/subprojects", tags=["subprojects"])


def _get_or_404(session, subproject_id: int) -> Subproject:
    subproject = session.get(Subproject, subproject_id)
    if subproject is None:
        raise HTTPException(status_code=404, detail="Subproject not found.")
    return subproject


@router.get("/{subproject_id}", response_model=SubprojectDetail)
def get_subproject(subproject_id: int, session: SessionDep) -> SubprojectDetail:
    subproject = _get_or_404(session, subproject_id)
    tickets = list(
        session.exec(
            select(Ticket)
            .where(Ticket.subproject_id == subproject_id)
            .order_by(Ticket.id)
        ).all()
    )
    return SubprojectDetail(
        id=subproject.id,  # type: ignore[arg-type]
        project_id=subproject.project_id,
        name=subproject.name,
        context_brief=subproject.context_brief,
        status=subproject.status,
        tickets=[TicketRead.model_validate(t) for t in tickets],
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


@router.post(
    "/{subproject_id}/tickets",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    subproject_id: int,
    payload: TicketCreate,
    session: SessionDep,
) -> Ticket:
    _get_or_404(session, subproject_id)

    ticket = Ticket(
        subproject_id=subproject_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        assignee=payload.assignee,
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.TICKET_CREATED,
            entity="ticket",
            entity_id=ticket.id,  # type: ignore[arg-type]
            parent_id=subproject_id,
        )
    )
    return ticket
