# API Endpoints Specification

## Base Configuration
* **Base URL:** `http://localhost:8000/api/v1`
* **Auth:** `Authorization: Bearer <AGENT_API_KEY>` (Agent only)
* **Format:** `application/json`

## Real-Time Synchronization
* `GET /events` : Server-Sent Events (SSE) stream broadcasting `{action, entity, entity_id, parent_id}`.

## Projects
* `GET /projects` : Retrieve all projects.
* `POST /projects` : Create new project `(name, description)`.
* `GET /projects/{id}` : Retrieve project details.
* `DELETE /projects/{id}` : Hard-delete a project and cascade subprojects, tickets, comments, audit logs, and knowledge nodes.

## Subprojects (Contexts)
* `GET /projects/{project_id}/subprojects` : List subprojects.
* `POST /projects/{project_id}/subprojects` : Create subproject `(name, context_brief)`.
* `GET /subprojects/{id}` : Retrieve subproject context and nested tickets.
* `PATCH /subprojects/{id}` : Mutate subproject `(name, context_brief, status)`.
* `DELETE /subprojects/{id}` : Hard-delete a subproject and cascade tickets, comments, and audit logs.

## Tickets
* `POST /subprojects/{subproject_id}/tickets` : Create ticket `(title, description, assignee)`.
* `GET /tickets/{id}` : Retrieve ticket detail with comments and audit logs.
* `PATCH /tickets/{id}` : Mutate state `(status, assignee, mr_link)`.
* `DELETE /tickets/{id}` : Hard-delete a ticket and cascade comments and audit logs.
* `POST /tickets/{id}/mr` : Attach MR link or trigger branch generation.

## Comments
* `GET /tickets/{ticket_id}/comments` : Retrieve threaded discussion.
* `POST /tickets/{ticket_id}/comments` : Append comment `(author, content)`.

## Knowledge Nodes
* `GET /projects/{project_id}/knowledge` : Flat project knowledge-node list; clients reconstruct the tree by `parent_id`.
* `GET /projects/{project_id}/knowledge/context-trail?query=...` : Query-scored knowledge trail with suggested load order and child hints.
* `POST /projects/{project_id}/knowledge` : Create a knowledge node `(title, node_type, content, parent_id, source_refs)`.
* `GET /knowledge/{id}` : Retrieve one knowledge node.
* `PATCH /knowledge/{id}` : Mutate a knowledge node; parent changes are validated against cross-project links and cycles.
* `DELETE /knowledge/{id}` : Hard-delete a node and cascade descendants.

## Agent Integrations
* `GET /agent/context/{subproject_id}` : Specialized endpoint returning heavily flattened string of `context_brief` and current tasks, optimized for LLM token efficiency.
* `GET /agent/projects/{project_id}/knowledge` : Bearer-gated hierarchical knowledge outline optimized for agent orientation.
* `GET /agent/projects/{project_id}/context-trail?query=...` : Bearer-gated context trail rendered as markdown for fresh agent windows.
* `GET /agent/knowledge/{id}` : Bearer-gated single knowledge-node detail.
