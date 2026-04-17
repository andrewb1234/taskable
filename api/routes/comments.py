"""Threaded comment endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.events import Event, get_broadcaster
from api.models.entities import Comment, Ticket
from api.models.enums import SSEAction
from api.schemas import CommentCreate, CommentRead

router = APIRouter(prefix="/tickets", tags=["comments"])


def _require_ticket(session, ticket_id: int) -> Ticket:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


@router.get("/{ticket_id}/comments", response_model=list[CommentRead])
def list_comments(ticket_id: int, session: SessionDep) -> list[Comment]:
    _require_ticket(session, ticket_id)
    return list(
        session.exec(
            select(Comment)
            .where(Comment.ticket_id == ticket_id)
            .order_by(Comment.timestamp)
        ).all()
    )


@router.post(
    "/{ticket_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    ticket_id: int,
    payload: CommentCreate,
    session: SessionDep,
) -> Comment:
    ticket = _require_ticket(session, ticket_id)

    comment = Comment(
        ticket_id=ticket_id, author=payload.author, content=payload.content
    )
    session.add(comment)
    session.commit()
    session.refresh(comment)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.COMMENT_CREATED,
            entity="comment",
            entity_id=comment.id,  # type: ignore[arg-type]
            parent_id=ticket.id,
        )
    )
    return comment
