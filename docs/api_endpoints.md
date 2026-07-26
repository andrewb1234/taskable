# API Endpoints Specification

## Base Configuration
* **Base URL:** `http://localhost:8000/api/v1`
* **Auth:** HttpOnly session cookie for the UI or
  `Authorization: Bearer <TASKABLE_API_KEY>` for MCP/agent callers
* **Format:** `application/json`

## Service Operations

These endpoints are outside the `/api/v1` base:

* `GET /healthz` : Lightweight process liveness and immutable release identity.
* `GET /readyz` : Database/realtime readiness; returns `503` when traffic
  should not be routed to the instance.
* `GET /internal/metrics` : Prometheus exposition, hidden with `404` until a
  dedicated metrics token is configured and then protected by bearer auth.

Every HTTP response includes a server-generated `X-Request-ID`.

## Real-Time Synchronization
* `GET /events` : Authenticated SSE stream broadcasting
  `{action, entity, entity_id, parent_id, workspace_id}` invalidations.
  Initial connection, automatic reconnect, listener recovery, and subscriber
  overflow emit `SYNC_REQUIRED`; clients refetch authorized live state.
  Project-restricted API keys cannot subscribe to the workspace-wide stream.

## Workspaces and Data Lifecycle

* `GET /workspaces` : List the caller's workspace memberships, including pending-deletion recovery metadata.
* `POST /workspaces` : Create a workspace owned by the interactive caller.
* `GET /workspaces/{id}/members` : Owner-browser-only member listing.
* `POST|GET /workspaces/{id}/invitations` : Create a copy-once, hashed,
  expiring email-bound invitation or list invitation status.
* `DELETE /workspaces/{id}/invitations/{invitation_id}` : Revoke an active
  invitation.
* `POST /workspaces/invitations/accept` : Accept once from the invited
  verified-email browser account.
* `PATCH|DELETE /workspaces/{id}/members/{user_id}` : Change a non-owner human
  role or remove a member. Removal revokes the member's workspace API keys and
  all browser sessions.
* `POST /workspaces/{id}/ownership-transfer` : Atomically demote the current
  owner to `ADMIN` and promote an accepted member after exact-slug
  confirmation.
* `GET /workspaces/{id}/membership-events` : Owner-only access-change ledger.
* `GET /workspaces/{id}/export` : Owner-only interactive export with a SHA-256 response header; API keys are rejected.
* `POST /workspaces/{id}/deletion` : Owner-only deletion schedule requiring exact slug and a matching export from the preceding 24 hours.
* `POST /workspaces/{id}/restore` : Restore during the recovery window; revoked API keys remain revoked.
* `GET /workspaces/{id}/lifecycle-events` : Owner-only export/deletion/restore/purge ledger.

## Projects
* `GET /projects` : Retrieve all projects.
* `POST /projects` : Create new project `(name, description)`.
* `GET /projects/{id}` : Retrieve project details.
* `GET /projects/{id}/control-room` : Bounded project dashboard read model: compact subprojects with capped context previews, ticket aggregates, capped attention/in-flight lists, knowledge/proposal counts, and up to four resumable handoffs. It never includes complete subproject briefs, knowledge bodies, proposal payloads, or complete session history.
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
