# Database Schema Specification

## ORM Context
Target framework: `SQLModel` (FastAPI). Engine: `SQLite`. All datetime fields should default to `datetime.utcnow`.

## Entities & Attributes

### Project
* `id`: Integer, Primary Key
* `name`: String
* `description`: String, Optional
* `created_at`: DateTime

### Subproject (Sprint Context)
* `id`: Integer, Primary Key
* `project_id`: Integer, ForeignKey(`project.id`)
* `name`: String
* `context_brief`: String (Used by MCP for agent orientation)
* `status`: Enum (`PLANNING`, `ACTIVE`, `COMPLETED`)

### Ticket
* `id`: Integer, Primary Key
* `subproject_id`: Integer, ForeignKey(`subproject.id`)
* `title`: String
* `description`: String, Optional
* `status`: Enum (`TODO`, `IN_PROGRESS`, `BLOCKED`, `REVIEW`, `DONE`)
* `assignee`: Enum (`HUMAN`, `AGENT`, `UNASSIGNED`)
* `mr_link`: String, Optional (GitHub PR URL)

### Comment
* `id`: Integer, Primary Key
* `ticket_id`: Integer, ForeignKey(`ticket.id`)
* `author`: Enum (`HUMAN`, `AGENT`)
* `content`: String
* `timestamp`: DateTime

### AuditLog (Ledger)
* `id`: Integer, Primary Key
* `ticket_id`: Integer, ForeignKey(`ticket.id`)
* `action`: Enum (`STATUS_UPDATE`, `CONTENT_UPDATE`, `MR_LINKED`)
* `actor`: Enum (`HUMAN`, `AGENT`)
* `timestamp`: DateTime
