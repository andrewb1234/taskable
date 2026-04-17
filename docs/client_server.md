# Client-Server Interaction Flow

## Core Paradigm
The system utilizes a unidirectional data flow for state synchronization. All state mutations occur via standard REST calls, while real-time updates are broadcast to the frontend via Server-Sent Events (SSE).

## Interaction Lifecycle

### 1. State Initialization
* **Client/Agent:** Requests baseline state via `GET /subprojects/{id}`.
* **Server:** Returns the full contextual hierarchy (Subproject -> Tickets -> Comments).
* **Client (UI Only):** Establishes a persistent listening connection to `GET /events`.

### 2. State Mutation (Write Path)
* **Actor (UI or MCP):** Dispatches a state change (e.g., `PATCH /tickets/42`, body: `{"status": "IN_PROGRESS"}`).
* **Server:**
    1. Validates payload and commits the change to SQLite.
    2. Writes a corresponding entry to the `AuditLog`.
    3. Pushes an event to the internal SSE broadcaster.
    4. Returns `200 OK` with the updated entity to the calling actor.

### 3. Real-Time Synchronization (Read Path)
* **Server:** Broadcasts a lightweight event down the open SSE connection: 
  `{"action": "TICKET_UPDATED", "entity_id": 42}`
* **Client (UI):** 1. Receives the SSE event.
    2. Invalidates the local cache for the specific entity.
    3. Performs a targeted background refetch (`GET /tickets/42`) to update the Kanban board smoothly.
