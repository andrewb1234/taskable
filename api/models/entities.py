"""SQLModel persistent entities for Taskable.

Schema aligned to ``docs/db_schema.md``. Relationships are defined so
``GET /subprojects/{id}`` can return nested tickets and ``GET /tickets/{id}``
can return threaded comments in one round trip.

We deliberately do NOT use ``from __future__ import annotations`` here:
SQLAlchemy's relationship mapper introspects the type annotation at class
construction time and expects concrete generics (e.g. ``list["Subproject"]``)
rather than stringified PEP 563 forms.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

from api.models.enums import (
    ActorRole,
    AuditAction,
    KnowledgeNodeType,
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

    subprojects: List["Subproject"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    knowledge_nodes: List["KnowledgeNode"] = Relationship(
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
    tickets: List["Ticket"] = Relationship(
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
    comments: List["Comment"] = Relationship(
        back_populates="ticket",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    audit_logs: List["AuditLog"] = Relationship(
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


class KnowledgeNode(SQLModel, table=True):
    """Self-referential node in the per-project knowledge tree.

    Upstream of subprojects and tickets: this is where agents persist raw
    research material, compressed summaries, and drafted PRD/TDD artifacts
    for a project. A tree (single ``parent_id``) is sufficient for v1 —
    relaxing to a DAG would require a separate edges table.

    ``source_refs`` stores arbitrary string pointers (absolute file paths,
    URLs, or ``node:<id>`` breadcrumbs) so a human can trace a summary back
    to its origin without the agent having to re-read the raw content.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    parent_id: Optional[int] = Field(
        default=None, foreign_key="knowledgenode.id", index=True
    )

    title: str
    node_type: KnowledgeNodeType = Field(default=KnowledgeNodeType.RAW)
    content: str = Field(default="")
    source_refs: List[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False, default=list)
    )
    created_by: ActorRole = Field(default=ActorRole.AGENT)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    project: Optional[Project] = Relationship(back_populates="knowledge_nodes")
    parent: Optional["KnowledgeNode"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "KnowledgeNode.id"},
    )
    children: List["KnowledgeNode"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
