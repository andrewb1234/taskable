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


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TicketStatus] = None
    assignee: Optional[TicketAssignee] = None
    mr_link: Optional[str] = None


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subproject_id: int
    title: str
    description: Optional[str] = None
    status: TicketStatus
    assignee: TicketAssignee
    mr_link: Optional[str] = None


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
