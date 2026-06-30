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

from sqlalchemy import Column, JSON, String
from sqlmodel import Field, Relationship, SQLModel

from api.models.enums import (
    ActorRole,
    AuditAction,
    BlockedByCategory,
    KnowledgeNodeStatus,
    KnowledgeNodeType,
    SubprojectStatus,
    TicketAssignee,
    TicketStatus,
)
from api.utils.time import utcnow


class AgentSession(SQLModel, table=True):
    """Records an agent work session for handoff and audit purposes."""

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    intent: str = Field(default="")
    loaded_node_ids: List[int] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False, default=list)
    )
    started_at: datetime = Field(default_factory=utcnow, nullable=False)
    ended_at: Optional[datetime] = Field(default=None)
    handoff_note: Optional[str] = Field(default=None)
    status: str = Field(default="ACTIVE")

    project: Optional["Project"] = Relationship(back_populates="sessions")


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
    sessions: List["AgentSession"] = Relationship(
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
    blocked_by: Optional[BlockedByCategory] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    blocked_reason: Optional[str] = Field(default=None)
    source_refs: List[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False, default=list)
    )

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
    status: KnowledgeNodeStatus = Field(
        default=KnowledgeNodeStatus.CURRENT, sa_column=Column(String, nullable=False, default="CURRENT")
    )
    superseded_by: Optional[int] = Field(
        default=None, foreign_key="knowledgenode.id", index=True
    )
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
        sa_relationship_kwargs={"remote_side": "KnowledgeNode.id", "foreign_keys": "[KnowledgeNode.parent_id]"},
    )
    children: List["KnowledgeNode"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "foreign_keys": "[KnowledgeNode.parent_id]"},
    )
    proposals: List["KnowledgeProposal"] = Relationship(
        back_populates="node",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class User(SQLModel, table=True):
    """Registered user authenticated via Google OAuth."""

    id: Optional[int] = Field(default=None, primary_key=True)
    google_id: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    name: str
    avatar_url: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class ApiKey(SQLModel, table=True):
    """Per-user API key for agent/MCP authentication.

    The full key is shown once on creation and never stored. We persist only:
    - ``key_prefix`` (first 12 chars) for display/identification
    - ``key_hash`` (SHA-256 of the full key) for lookup/verification
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(default="Default")
    key_prefix: str = Field(index=True)
    key_hash: str = Field(unique=True, index=True)
    expires_at: Optional[datetime] = Field(default=None)
    last_used_at: Optional[datetime] = Field(default=None)
    revoked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    user: Optional[User] = Relationship()


class KnowledgeProposal(SQLModel, table=True):
    """Agent-submitted proposed change to a knowledge node, pending human review."""

    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: int = Field(foreign_key="knowledgenode.id", index=True)
    proposed_by: str = Field(default="AGENT")
    proposed_changes: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict)
    )
    rationale: str = Field(default="")
    status: str = Field(default="PENDING")
    reviewed_by: Optional[str] = Field(default=None)
    reviewed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    node: Optional[KnowledgeNode] = Relationship(back_populates="proposals")
