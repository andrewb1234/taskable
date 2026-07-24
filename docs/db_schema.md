# Database Schema Specification

## ORM Context
Target framework: `SQLModel` (FastAPI). Engine: `SQLite`. All datetime fields should default to `datetime.utcnow`.

## Entities & Attributes

### Workspace
* `id`: Integer, Primary Key
* `name`: String
* `slug`: String, Unique
* `created_at`: DateTime
* Relationships: owns `projects` and cascades `memberships`.

### WorkspaceMembership
* `id`: Integer, Primary Key
* `workspace_id`: Integer, ForeignKey(`workspace.id`)
* `user_id`: Integer, ForeignKey(`user.id`)
* `role`: Enum (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`, `SERVICE`)
* `created_at`: DateTime
* Constraint: unique (`workspace_id`, `user_id`).

### Project
* `id`: Integer, Primary Key
* `workspace_id`: Integer, ForeignKey(`workspace.id`). Nullable only as a
  temporary bridge for legacy databases awaiting safe ownership assignment.
* `name`: String
* `description`: String, Optional
* `created_at`: DateTime
* Relationships: cascades `subprojects` and `knowledge_nodes`.

### Subproject (Sprint Context)
* `id`: Integer, Primary Key
* `project_id`: Integer, ForeignKey(`project.id`)
* `name`: String
* `context_brief`: String (Used by MCP for agent orientation)
* `status`: Enum (`PLANNING`, `ACTIVE`, `COMPLETED`)
* Relationships: cascades `tickets`.

### Ticket
* `id`: Integer, Primary Key
* `subproject_id`: Integer, ForeignKey(`subproject.id`)
* `title`: String
* `description`: String, Optional
* `status`: Enum (`TODO`, `IN_PROGRESS`, `BLOCKED`, `REVIEW`, `DONE`)
* `assignee`: Enum (`HUMAN`, `AGENT`, `UNASSIGNED`)
* `mr_link`: String, Optional (GitHub PR URL)
* `source_refs`: JSON array of strings
* `claimed_by`: String, Optional
* `claimed_at`: DateTime, Optional
* `lease_expires_at`: DateTime, Optional
* Relationships: cascades `comments` and `audit_logs`.

### TicketDependency
* `ticket_id`: Integer, ForeignKey(`ticket.id`), composite Primary Key
* `depends_on_ticket_id`: Integer, ForeignKey(`ticket.id`), composite Primary Key
* Constraint: unique (`ticket_id`, `depends_on_ticket_id`).

### Comment
* `id`: Integer, Primary Key
* `ticket_id`: Integer, ForeignKey(`ticket.id`)
* `author`: Enum (`HUMAN`, `AGENT`)
* `content`: String
* `timestamp`: DateTime

### AuditLog (Ledger)
* `id`: Integer, Primary Key
* `ticket_id`: Integer, ForeignKey(`ticket.id`)
* `action`: Enum (`STATUS_UPDATE`, `CONTENT_UPDATE`, `MR_LINKED`,
  `TICKET_CLAIMED`, `TICKET_REQUEUED`)
* `actor`: Enum (`HUMAN`, `AGENT`)
* `timestamp`: DateTime

### KnowledgeNode
* `id`: Integer, Primary Key
* `project_id`: Integer, ForeignKey(`project.id`)
* `parent_id`: Integer, Optional, self-ForeignKey(`knowledgenode.id`)
* `title`: String
* `node_type`: Enum (`RAW`, `SUMMARY`, `PRD`, `TDD`)
* `content`: String
* `source_refs`: JSON array of strings (`/path`, URL, or `node:<id>`)
* `created_by`: Enum (`HUMAN`, `AGENT`)
* `created_at`: DateTime
* `updated_at`: DateTime
* Relationships: cascades `children`.
