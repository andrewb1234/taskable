"""SQLModel persistent entities for Taskable.

Schema aligned to ``docs/db_schema.md``. Relationships are defined so
``GET /subprojects/{id}`` can return nested tickets and ``GET /tickets/{id}``
can return threaded comments in one round trip.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from api.models.enums import (
    ActorRole,
    AuditAction,
    SubprojectStatus,
    TicketAssignee,
    TicketStatus,
)
from api.utils.time import utcnow


class Project(SQLModel, table=True):
    """Top-level container grouping a set of subprojects."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    subprojects: list["Subproject"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Subproject(SQLModel, table=True):
    """Sprint-style context carrying a goal brief and ordered tickets."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    name: str
    context_brief: str = Field(default="")
    status: SubprojectStatus = Field(default=SubprojectStatus.PLANNING)

    project: Optional[Project] = Relationship(back_populates="subprojects")
    tickets: list["Ticket"] = Relationship(
        back_populates="subproject",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Ticket(SQLModel, table=True):
    """Actionable unit tracked on the Kanban board."""

    id: Optional[int] = Field(default=None, primary_key=True)
    subproject_id: int = Field(foreign_key="subproject.id", index=True)
    title: str
    description: Optional[str] = Field(default=None)
    status: TicketStatus = Field(default=TicketStatus.TODO)
    assignee: TicketAssignee = Field(default=TicketAssignee.UNASSIGNED)
    mr_link: Optional[str] = Field(default=None)

    subproject: Optional[Subproject] = Relationship(back_populates="tickets")
    comments: list["Comment"] = Relationship(
        back_populates="ticket",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    audit_logs: list["AuditLog"] = Relationship(
        back_populates="ticket",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Comment(SQLModel, table=True):
    """Threaded discussion attached to a ticket."""

    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    author: ActorRole
    content: str
    timestamp: datetime = Field(default_factory=utcnow, nullable=False)

    ticket: Optional[Ticket] = Relationship(back_populates="comments")


class AuditLog(SQLModel, table=True):
    """Immutable ledger of ticket state changes.

    Exactly mirrors ``docs/db_schema.md`` — no diff payload — so audits stay
    cheap to write. If we need before/after values later, extend here.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    action: AuditAction
    actor: ActorRole
    timestamp: datetime = Field(default_factory=utcnow, nullable=False)

    ticket: Optional[Ticket] = Relationship(back_populates="audit_logs")
