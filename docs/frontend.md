# Frontend Architecture Specification

## Tech Stack
* **Framework:** React (Vite, TypeScript).
* **Styling:** Tailwind CSS.
* **UI Components:** `shadcn/ui` (Radix UI primitives).

## State Management & Real-time
* **Global State:** Minimal. Use React Context for active `project_id` and `subproject_id`.
* **Data Fetching:** Standard `fetch` (or a lightweight library like `SWR`) with targeted cache invalidation.
* **Real-time Sync:** Implement a global `useSSE` hook listening to `GET /api/v1/events`. Upon receiving an event payload (e.g., `{"action": "TICKET_UPDATED", "entity_id": 42}`), invalidate the local cache for that entity and trigger a silent background refetch to update the UI.

## Component Tree Structure
* `AppLayout`: Main screen wrapper.
  * `Sidebar`: Project and Subproject navigation tree.
  * `Workspace`: Active context area.
    * `SubprojectHeader`: Displays `name` and `context_brief`.
    * `KanbanBoard`: Horizontal flex container.
      * `KanbanColumn`: Filters active tickets by `status`.
        * `TicketCard`: Summary view (title, assignee avatar, MR link indicator).
    * `TicketModal`: Detailed overlay.
      * `TicketEditor`: Editable description.
      * `MetadataPane`: Assignee, Status, and MR link management.
      * `CommentThread`: Chat interface for Human/Agent discussion.
  * `ProfilePage`: Identity and owner controls.
    * Creates scoped, expiring workspace API keys and lists revoked keys.
    * Lists and revokes browser sessions.
    * `Data & Recovery` downloads hashed owner exports, enables deletion only
      after a fresh export, requires the exact workspace slug, lists pending
      purge deadlines, and restores workspaces during the recovery window.
    * Deleted workspaces never appear in API-key creation options, and the UI
      states that restoration does not reactivate revoked keys.

## Styling Guidelines
* Utilize `shadcn/ui` for complex interactives (Dialog, Select, Dropdown).
* Optimize layout for desktop, favoring high information density over excessive whitespace.
