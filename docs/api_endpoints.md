# API Endpoints Specification

## Base Configuration
* **Base URL:** `http://localhost:8000/api/v1`
* **Auth:** `Authorization: Bearer <AGENT_API_KEY>` (Agent only)
* **Format:** `application/json`

## Real-Time Synchronization
* `GET /events` : Server-Sent Events (SSE) stream broadcasting `{action, entity, id}`.

## Projects
* `GET /projects` : Retrieve all projects.
* `POST /projects` : Create new project `(name, description)`.
* `GET /projects/{id}` : Retrieve project details.

## Subprojects (Contexts)
* `GET /projects/{project_id}/subprojects` : List subprojects.
* `POST /projects/{project_id}/subprojects` : Create subproject `(name, context_brief)`.
* `GET /subprojects/{id}` : Retrieve subproject context and nested tickets.

## Tickets
* `POST /subprojects/{subproject_id}/tickets` : Create ticket `(title, description, assignee)`.
* `PATCH /tickets/{id}` : Mutate state `(status, assignee, mr_link)`.
* `POST /tickets/{id}/mr` : Attach MR link or trigger branch generation.

## Comments
* `GET /tickets/{ticket_id}/comments` : Retrieve threaded discussion.
* `POST /tickets/{ticket_id}/comments` : Append comment `(author, content)`.

## Agent Integrations
* `GET /agent/context/{subproject_id}` : Specialized endpoint returning heavily flattened string of `context_brief` and current tasks, optimized for LLM token efficiency.
