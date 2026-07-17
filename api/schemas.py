"""Pydantic request/response DTOs.

Kept separate from SQLModel table classes so input validation is explicit and
response payloads can embed relations without accidental recursion.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

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


# ---- Project --------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime


# ---- Subproject -----------------------------------------------------------


class SubprojectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    context_brief: str = ""
    status: SubprojectStatus = SubprojectStatus.PLANNING


class SubprojectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    context_brief: Optional[str] = None
    status: Optional[SubprojectStatus] = None


class SubprojectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    context_brief: str
    status: SubprojectStatus


# ---- Ticket ---------------------------------------------------------------


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    assignee: TicketAssignee = TicketAssignee.UNASSIGNED
    status: TicketStatus = TicketStatus.TODO
    source_refs: list[str] = Field(default_factory=list)
    depends_on: list[int] = Field(default_factory=list)


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TicketStatus] = None
    assignee: Optional[TicketAssignee] = None
    mr_link: Optional[str] = None
    blocked_by: Optional[BlockedByCategory] = None
    blocked_reason: Optional[str] = None
    source_refs: Optional[list[str]] = None
    depends_on: Optional[list[int]] = None


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subproject_id: int
    title: str
    description: Optional[str] = None
    status: TicketStatus
    assignee: TicketAssignee
    mr_link: Optional[str] = None
    blocked_by: Optional[BlockedByCategory] = None
    blocked_reason: Optional[str] = None
    source_refs: list[str] = Field(default_factory=list)
    depends_on: list[int] = Field(default_factory=list)
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
    lease_expires_at: Optional[datetime] = None


class MRLinkPayload(BaseModel):
    url: str = Field(min_length=1)


# ---- Comment --------------------------------------------------------------


class CommentCreate(BaseModel):
    author: ActorRole
    content: str = Field(min_length=1)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    author: ActorRole
    content: str
    timestamp: datetime


# ---- AuditLog (read-only exposure) ---------------------------------------


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    action: AuditAction
    actor: ActorRole
    timestamp: datetime


# ---- Compound reads ------------------------------------------------------


class SubprojectDetail(SubprojectRead):
    """Returned from ``GET /subprojects/{id}`` — includes ordered tickets."""

    tickets: list[TicketRead] = Field(default_factory=list)


class TicketDetail(TicketRead):
    """Returned from ``GET /tickets/{id}`` — includes threaded comments."""

    comments: list[CommentRead] = Field(default_factory=list)
    audit_logs: list[AuditLogRead] = Field(default_factory=list)


class ClaimPayload(BaseModel):
    worker_id: str = Field(min_length=1, max_length=200)


class HeartbeatPayload(BaseModel):
    worker_id: str = Field(min_length=1, max_length=200)
    extend_seconds: int = Field(default=600, ge=60, le=86400)


# ---- KnowledgeNode -------------------------------------------------------


class KnowledgeNodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    node_type: KnowledgeNodeType = KnowledgeNodeType.RAW
    content: str = ""
    parent_id: Optional[int] = None
    source_refs: list[str] = Field(default_factory=list)


class KnowledgeNodeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    node_type: Optional[KnowledgeNodeType] = None
    status: Optional[KnowledgeNodeStatus] = None
    superseded_by: Optional[int] = None
    content: Optional[str] = None
    parent_id: Optional[int] = None
    source_refs: Optional[list[str]] = None


class KnowledgeNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    parent_id: Optional[int] = None
    title: str
    node_type: KnowledgeNodeType
    status: KnowledgeNodeStatus = KnowledgeNodeStatus.CURRENT
    superseded_by: Optional[int] = None
    content: str
    source_refs: list[str] = Field(default_factory=list)
    created_by: ActorRole
    created_at: datetime
    updated_at: datetime


# ---- Context trails ------------------------------------------------------


class ContextTrailSegment(BaseModel):
    """Compact node identity used inside a breadcrumb path or load order."""

    id: int
    title: str
    node_type: KnowledgeNodeType


class ContextTrailChildHint(ContextTrailSegment):
    """Nearby child node that may be worth drilling into next."""

    content_preview: str = ""
    source_refs: list[str] = Field(default_factory=list)


class ContextTrailItem(BaseModel):
    """One matched branch in a contextual knowledge search."""

    id: int
    title: str
    node_type: KnowledgeNodeType
    parent_id: Optional[int] = None
    path: list[ContextTrailSegment] = Field(default_factory=list)
    score: int
    matched_terms: list[str] = Field(default_factory=list)
    reason: str
    content_preview: str = ""
    source_refs: list[str] = Field(default_factory=list)
    child_count: int = 0
    children: list[ContextTrailChildHint] = Field(default_factory=list)


class ContextTrailRead(BaseModel):
    """Response for a task-intent search over the knowledge tree."""

    project_id: int
    project_name: str
    query: str
    load_order: list[ContextTrailSegment] = Field(default_factory=list)
    items: list[ContextTrailItem] = Field(default_factory=list)


# ---- KnowledgeProposal ---------------------------------------------------


class KnowledgeProposalCreate(BaseModel):
    proposed_changes: dict
    rationale: str = ""


class KnowledgeProposalReview(BaseModel):
    action: str  # "accept" or "reject"
    reviewed_by: str = "HUMAN"


class KnowledgeProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    proposed_by: str
    proposed_changes: dict
    rationale: str
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


# ---- AgentSession --------------------------------------------------------


class AgentSessionCreate(BaseModel):
    intent: str = ""
    loaded_node_ids: list[int] = Field(default_factory=list)


class AgentSessionUpdate(BaseModel):
    loaded_node_ids: Optional[list[int]] = None
    handoff_note: Optional[str] = None
    status: Optional[str] = None


class AgentSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    intent: str
    loaded_node_ids: list[int] = Field(default_factory=list)
    started_at: datetime
    ended_at: Optional[datetime] = None
    handoff_note: Optional[str] = None
    status: str


# ---- Knowledge tickets backlink ------------------------------------------


class TicketRef(BaseModel):
    """Compact ticket reference returned from knowledge backlink queries."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: TicketStatus
    assignee: TicketAssignee
    subproject_id: int
