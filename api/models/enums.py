"""String enumerations shared across models, routes, and MCP tools."""

from __future__ import annotations

from enum import Enum


class SubprojectStatus(str, Enum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class TicketStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    REVIEW = "REVIEW"
    DONE = "DONE"


class TicketAssignee(str, Enum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"
    UNASSIGNED = "UNASSIGNED"


class ActorRole(str, Enum):
    """Used for Comment.author and AuditLog.actor (no UNASSIGNED here)."""

    HUMAN = "HUMAN"
    AGENT = "AGENT"


class AuditAction(str, Enum):
    STATUS_UPDATE = "STATUS_UPDATE"
    CONTENT_UPDATE = "CONTENT_UPDATE"
    MR_LINKED = "MR_LINKED"


class SSEAction(str, Enum):
    """Vocabulary of events broadcast over ``GET /api/v1/events``."""

    PROJECT_CREATED = "PROJECT_CREATED"
    SUBPROJECT_CREATED = "SUBPROJECT_CREATED"
    SUBPROJECT_UPDATED = "SUBPROJECT_UPDATED"
    TICKET_CREATED = "TICKET_CREATED"
    TICKET_UPDATED = "TICKET_UPDATED"
    COMMENT_CREATED = "COMMENT_CREATED"
    MR_LINKED = "MR_LINKED"
