# Client-Server Interaction Flow

## Core Paradigm
The system uses unidirectional invalidation for state synchronization. All
state mutations occur through REST. Content-free invalidations reach the
frontend through Server-Sent Events (SSE), and the UI refetches authorized
state.

## Interaction Lifecycle

### 1. State Initialization
* **Client/Agent:** Requests baseline state via `GET /subprojects/{id}`.
* **Server:** Returns the full contextual hierarchy (Subproject -> Tickets -> Comments).
* **Client (UI Only):** Establishes a persistent listening connection to
  `GET /events`.

### 2. State Mutation (Write Path)
* **Actor (UI or MCP):** Dispatches a state change (e.g., `PATCH /tickets/42`, body: `{"status": "IN_PROGRESS"}`).
* **Server:**
    1. Validates payload and commits the change to SQLite or PostgreSQL.
    2. Writes a corresponding entry to the `AuditLog`.
    3. Publishes a workspace-tagged invalidation. SQLite/local deployments
       fan out in-process; PostgreSQL also uses direct LISTEN/NOTIFY so every
       API process receives it.
    4. Returns `200 OK` with the updated entity to the calling actor.

### 3. Real-Time Synchronization (Read Path)
* **Server:** Rechecks current workspace membership with a short database
  session, then broadcasts:
  `{"action":"TICKET_UPDATED","entity":"ticket","entity_id":42,"parent_id":7,"workspace_id":3}`.
* **Client (UI):** 1. Receives the SSE event.
    2. Invalidates the local cache for the specific entity.
    3. Performs a targeted background refetch (`GET /tickets/42`) to update the Kanban board smoothly.

## Delivery and replay policy

SSE messages are invalidation hints, not a durable event log or an
exactly-once contract. Every initial connection and automatic `EventSource`
reconnect receives `SYNC_REQUIRED`; the client refetches all currently visible
authorized state. A slow subscriber whose bounded queue overflows receives the
same signal after stale queued deltas are discarded. A PostgreSQL listener
reconnect also signals every local subscriber to resync.

This makes missed or duplicated notifications recoverable without placing
tenant content in the shared transport. Business audit history stays in the
database; do not reconstruct it from SSE.

## PostgreSQL connection requirement

LISTEN is session-scoped and requires a direct PostgreSQL connection.
`REALTIME_DATABASE_URL` can provide one when the application uses a
transaction pooler. Neon `-pooler` hostnames are converted to the corresponding
documented direct hostname automatically when no override is set.
