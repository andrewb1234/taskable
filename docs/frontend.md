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
* Follow [`ui_design_system.md`](ui_design_system.md) for semantic tokens,
  brand components, ticket/actor states, focus treatment, motion, and
  reduced-motion behavior.
* Use raw palette utilities only for genuinely local illustrations. Product
  state and reusable surfaces must use documented semantic tokens.

## Routes and provider ownership

The application intentionally uses the browser History API without a routing
dependency:

- `/` is the public landing page for unauthenticated visitors.
- `/app` is the authenticated workspace or sign-in entry.
- Authenticated visits to `/` replace-navigate to `/app`.
- Invitation tokens arrive in the URL fragment, move immediately into
  same-origin session storage, and continue through authentication without
  entering request logs.

`AuthProvider` owns the current browser session and the authentication methods
enabled for the current environment. Provider flags describe authentication
methods, not deployment topology: Google availability must be presented as
“Google sign-in,” and local-key availability as “API-key sign-in.” The UI must
never advertise a method whose provider flag is false.

`WorkspaceProvider` wraps both `AppLayout` and `ProfilePage`. This keeps the
selected project, subproject, and workspace view stable across a profile
round-trip. Route-level components are loaded with `React.lazy` and
`Suspense`, keeping the public landing payload independent from authenticated
workbench code.

## Landing proof contract

The public landing page explains recovery with a static, illustrative
project-state ledger rather than a simulated product interface. Its sequence
must preserve the real coordination boundary:

1. agents read scoped knowledge and claim separate ready tickets;
2. a missing heartbeat allows a lease to expire, but does not transfer work;
3. an explicit requeue clears the stale worker and lease before another claim;
4. the new worker inspects existing code, external effects, and evidence;
5. independent review records the accepted outcome and updates durable
   knowledge.

The proof must remain complete without autoplay, timers, screenshots, or a
client-side state machine. Lease recovery prevents indefinite stale ownership;
it does not promise exactly-once execution.

## Authenticated information hierarchy

The Control Room answers operational questions before explaining the product:

1. work that needs human judgment;
2. work currently in flight and its owner;
3. a compact all-status distribution;
4. subproject execution boundaries;
5. actionable knowledge review or explicit handoffs, only when present; and
6. project brief and aggregate ownership under progressive disclosure.

Ticket claims are the source of truth for work in flight. Agent-session records
exist only when a client explicitly starts and checkpoints a session, so they
must not be presented as a complete live-agent monitor. The UI exposes
non-empty handoffs as recovery information and states that active ticket work
appears under Work in flight.

## Data loading and realtime invalidation

`useAsync` gives each mounted surface loading, data, error, and refetch state,
with an optional small shared TTL cache that deduplicates in-flight reads and
keeps recently visited views warm. Loading and error states use `role="status"`
and `role="alert"` where a screen-reader announcement is required. The cache is
cleared before an authenticated identity change is rendered, so data is never
reused across browser-session principals.

The Control Room uses one bounded `GET /projects/{id}/control-room` read model
instead of loading full knowledge-node bodies, proposal payloads, and agent
session history to render dashboard counts. It contains compact subprojects
with server-capped context previews, ticket aggregates, capped triage lists,
and at most four resumable handoffs; Kanban and Knowledge retain their detail
endpoints for drill-in work.

`AppLayout` owns the single SSE subscription and passes the latest validated
event into mounted workbench surfaces. The Control Room performs one
project-scoped summary refresh for an affected event; detail surfaces refetch
only the resource family they need. `SYNC_REQUIRED` is the exception: every
mounted resource refetches because incremental continuity is no longer
guaranteed. The stream also evicts affected warm cache entries even when their
views are not mounted; ticket events clear the small Control Room cache family
because the realtime payload names a subproject rather than its project.
Duplicate consumers can share an invalidation read before it starts, while an
invalidation arriving during an active refresh queues one trailing read so
rapid agent updates cannot be hidden by request deduplication.
Mutations remain ordinary REST requests; an SSE event is an invalidation
signal, not the stored source of truth.

## Responsive workspace

Desktop uses three persisted resizable splits:

| Storage key | Pane |
| --- | --- |
| `taskable.sidebar.width` | workspace navigation |
| `taskable.knowledge.treeWidth` | knowledge map |
| `taskable.kanban.headerHeight` | Kanban context header |

`ResizableSplit` supports pointer and keyboard resizing, clamps the first pane
against both its own bounds and the space required by the second pane, persists
only completed pointer/keyboard changes, and continues without persistence when
storage is unavailable. Pointer cancellation and lost capture end a drag
cleanly.

Below the medium breakpoint, the sidebar becomes a focus-trapped drawer,
Knowledge becomes a map-to-node drill-down, and workspace view tabs retain
44-pixel touch targets while truncating labels rather than overflowing. Narrow
tests assert local element containment as well as document width because
`overflow-hidden` can otherwise conceal collisions.

Authenticated `/app` surfaces own the dynamic viewport and lock page-level
scrolling and overscroll while mounted. Scrolling belongs to the explicit
Control Room, Knowledge, Kanban, profile, drawer, and dialog regions inside the
shell. The public landing and sign-in surfaces remain document-scrolling pages.

## Accessibility and browser regression contract

- Landing and application shells provide skip links to their main regions.
- Every page has one visible level-one heading at each responsive layout.
- Dialogs, fields, icon controls, disclosure summaries, and destructive
  actions have explicit accessible names.
- Knowledge hierarchy is a nested semantic list with ordinary disclosure
  buttons; it does not claim the ARIA tree pattern without tree keyboard
  behavior.
- State is always conveyed by text or icon in addition to color.
- Product controls provide at least a 44-pixel target on narrow viewports.
- Reduced motion removes optional entry/state animations without globally
  disabling every browser transition.

All Playwright specs import `tests/uiFixture.ts`. Its automatic guard fails a
test on uncaught page errors or `console.error`, including errors that do not
otherwise change the DOM. Browser-generated “Failed to load resource” lines are
excluded because expected 401/404/500 responses are asserted through their
visible recovery states; application-authored console errors remain failures.
Tests prefer accessible roles and labels; test IDs are reserved for stable
domain objects or regions that have no suitable semantic selector.
