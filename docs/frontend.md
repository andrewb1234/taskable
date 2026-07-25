# Frontend Architecture Specification

## Tech Stack
* **Framework:** React (Vite, TypeScript).
* **Styling:** Tailwind CSS.
* **UI Components:** `shadcn/ui` (Radix UI primitives).

## State Management & Real-time
* **Global State:** Minimal. Use React Context for active `project_id` and `subproject_id`.
* **Data Fetching:** Standard `fetch` (or a lightweight library like `SWR`) with targeted cache invalidation.
* **Real-time Sync:** The global `useSSE` hook listens to
  `GET /api/v1/events`. Entity invalidations trigger targeted background
  refetches. `SYNC_REQUIRED` on connect, reconnect, transport recovery, or
  subscriber overflow refreshes every mounted data surface and clears stale
  project/subproject selections.

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
    * `WorkspaceMembersSection` lets owners create copy-once invitation links,
      list and revoke pending invitations, change human roles, remove members,
      and perform a typed-confirmation ownership transfer.
    * Invitation tokens travel in the URL fragment, are moved immediately to
      same-origin session storage across OAuth, and are posted in the accept
      request body rather than sent in URL/query logs.
    * `Data & Recovery` downloads hashed owner exports, enables deletion only
      after a fresh export, requires the exact workspace slug, lists pending
      purge deadlines, and restores workspaces during the recovery window.
    * Deleted workspaces never appear in API-key creation options, and the UI
      states that restoration does not reactivate revoked keys.

## Styling Guidelines
* Utilize `shadcn/ui` for complex interactives (Dialog, Select, Dropdown).
* Optimize layout for desktop, favoring high information density over excessive whitespace.
