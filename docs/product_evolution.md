# Product Evolution: From Task Tracker to Shared Mental Model

## Thesis

The current product gets the foundation right: agents forget, structure compensates. By externalizing state into a real database with structured entities and a defined MCP tool surface, both human and agent operate on the same source of truth rather than trusting in-context summaries or ad-hoc files.

The context trails feature (current branch) is the inflection point. It pushes the product from *task tracker with agent-readable context* toward something more valuable: a **persistent shared mental model that survives session boundaries**.

The gap is that the knowledge tree is currently human-initialized and agent-readable, but not **agent-improvable with human oversight**. The proposals below close that gap. If implemented together, you get a system where each agent session leaves the knowledge tree slightly more complete than it found it, and the human acts as editor rather than author.

---

## Proposals

### 1. Session Checkpointing

**What**
A lightweight session lifecycle — `start_session` and `end_session` MCP tools that record what a given agent window loaded, what it intended, and what it left unfinished.

**Why**
Right now, every fresh agent window re-queries from scratch. There's no record of "last session loaded nodes 3, 7, 12, worked ticket #44, and stopped because auth flow was unclear." The human can infer this from audit logs and comments, but that's forensic reconstruction after the fact. A first-class session concept makes handoffs explicit and machine-readable.

The PRD mentions "checkpoint what they loaded" but there's no tool for it. This is the missing implementation.

**What's required**

*Backend:*
- New `AgentSession` model: `id`, `project_id`, `intent` (text), `loaded_node_ids` (JSON array), `started_at`, `ended_at`, `handoff_note` (text), `status` (`ACTIVE`, `COMPLETE`, `INTERRUPTED`)
- `POST /agent/sessions` — create session, record intent and initial node load list
- `PATCH /agent/sessions/{id}` — update loaded nodes mid-session, close with handoff note
- `GET /projects/{id}/sessions` — human-facing session history

*MCP tools:*
- `start_session(project_id, intent) -> session_id`
- `checkpoint_session(session_id, loaded_node_ids)` — call after each `find_context_trail` / `read_knowledge_node` batch
- `end_session(session_id, handoff_note)` — called before the agent window closes

*Frontend:*
- Session history panel on the project view showing intent, nodes loaded, handoff note, and duration
- Visual indicator when the last session ended with `INTERRUPTED` status (human knows to check the handoff note before assigning new work)

---

### 2. Knowledge Update Proposals (Trust Layer)

**What**
Replace the hard-overwrite `update_knowledge_node` with a proposal flow. Agents submit proposed changes with a rationale; humans approve or reject from the UI. Direct updates remain available for the human writing from the UI.

**Why**
`update_knowledge_node` is the highest-risk tool in the MCP surface. If an agent operates on stale context and silently overwrites a PRD node, the corruption is invisible until something downstream breaks. The human's biggest risk in this product is trusting agent-written context without a review step.

A proposal layer makes agent contributions visible as diffs rather than silent overwrites. It also creates a natural feedback loop: the pattern of accepted vs. rejected proposals tells you where agent judgment is reliable and where it isn't.

**What's required**

*Backend:*
- New `KnowledgeProposal` model: `id`, `node_id`, `proposed_by` (bearer token / "AGENT"), `proposed_changes` (JSON sparse patch), `rationale` (text), `status` (`PENDING`, `ACCEPTED`, `REJECTED`), `reviewed_by`, `reviewed_at`
- `POST /knowledge/{id}/proposals` — agent submits a proposed update
- `GET /projects/{id}/knowledge/proposals` — human reviews pending proposals
- `PATCH /knowledge/proposals/{id}` — human accepts (applies patch) or rejects (with optional note)
- SSE event: `KNOWLEDGE_PROPOSAL_CREATED` so the UI surfaces it immediately

*MCP tools:*
- `propose_knowledge_update(node_id, changes, rationale) -> proposal_id` — replaces direct `update_knowledge_node` calls from agent flows where confidence is low
- Keep `update_knowledge_node` for high-confidence agent writes (e.g., appending a source ref after reading a file), but add an optional `requires_review: bool` flag

*Frontend:*
- Proposal review queue in the knowledge panel — shows proposed diff, rationale, accept/reject buttons
- Badge on knowledge nodes with pending proposals
- Accepted/rejected proposal history on each node (for auditability)

---

### 3. Ticket ↔ Knowledge Linkage

**What**
A `source_refs` field on tickets that links them to specific knowledge nodes — mirroring the field already on knowledge nodes.

**Why**
Currently, the knowledge tree and the ticket system are loosely coupled: a subproject brief provides ambient context, but there's no way to record "this ticket exists because of PRD node #42" or "this implementation decision was driven by TDD node #7." That traceability is exactly what makes the knowledge tree valuable over time. Without it, the tree and the tickets drift into separate artifacts with no shared structure.

Closing this loop also enables a useful query: *show me all tickets that were derived from this PRD node*, which is the kind of impact analysis that makes refactoring or scope changes tractable.

**What's required**

*Backend:*
- Add `source_refs` field to the `Ticket` model (JSON array of `{node_id, label}` pairs — same shape as on `KnowledgeNode`)
- Update `POST /subprojects/{id}/tickets` and `PATCH /tickets/{id}` to accept `source_refs`
- New query: `GET /knowledge/{id}/tickets` — returns all tickets referencing this node

*MCP tools:*
- Update `create_ticket` to accept optional `source_refs` parameter
- Update `update_ticket_status` or add `update_ticket` to allow patching `source_refs`

*Frontend:*
- Source refs display on ticket detail (clickable links to knowledge nodes)
- Backlink section on knowledge node detail showing derived tickets
- Option to create a ticket directly from a knowledge node (pre-populates the source ref)

---

### 4. Structured Blocker Taxonomy

**What**
Add a `blocked_by` enum field to tickets with a fixed set of blocker categories, alongside the existing free-text comment mechanism.

**Why**
When an agent sets a ticket to `BLOCKED`, the reason lives in a comment the human has to find and read. At scale — or even with a dozen active tickets — triaging blocked tickets means opening each one. A structured `blocked_by` field lets the UI filter and prioritize human intervention without reading prose.

It also gives agents a cleaner signal: before starting work on a ticket, check if it's `BLOCKED` by `WAITING_HUMAN` (needs clarification now) vs. `WAITING_DEPENDENCY` (will unblock itself) vs. `AMBIGUOUS_REQUIREMENT` (needs knowledge tree update before code).

**What's required**

*Backend:*
- Add `blocked_by` enum to `Ticket` model: `WAITING_HUMAN`, `WAITING_DEPENDENCY`, `AMBIGUOUS_REQUIREMENT`, `EXTERNAL`, `null` (not blocked)
- Add `blocked_reason` optional text field for the agent's short explanation
- `PATCH /tickets/{id}` accepts both fields; `blocked_by` must be non-null when `status=BLOCKED`, must be null otherwise (validated)
- Include both fields in the `read_subproject_context` agent endpoint output

*MCP tools:*
- Update `update_ticket_status` to require `blocked_by` when `status="BLOCKED"`, accept optional `blocked_reason`

*Frontend:*
- Blocker badge on ticket cards in the board view (color-coded by category)
- Filter panel: show only tickets blocked on human input
- Tooltip on the badge shows `blocked_reason`

---

### 5. Structured Subproject Brief

**What**
Break `context_brief` from a single free-text blob into structured fields: `goal`, `constraints`, `out_of_scope`, and `open_questions`.

**Why**
The context brief is the most-read artifact in the system — every `read_subproject_context` call returns it. Agents currently have to infer scope and constraints from prose, which is error-prone. An agent that misreads "out of scope" from an ambiguous paragraph is a real failure mode.

Structured fields also make the brief easier to fill out for humans (clear prompts beat a blank textarea) and easier to update incrementally (adding an open question doesn't require rewriting the whole blob).

**What's required**

*Backend:*
- Replace `context_brief: str` on `Subproject` model with four nullable text fields: `goal`, `constraints`, `out_of_scope`, `open_questions`
- Migration: move existing `context_brief` content into `goal` field for existing rows
- Update `read_subproject_context` agent endpoint to format these as labeled sections in its output
- `PATCH /subprojects/{id}` accepts each field independently (sparse update)

*MCP tools:*
- Update `create_subproject` signature: `goal` replaces `context_brief`; add optional `constraints`, `out_of_scope`, `open_questions`
- Add `update_subproject(subproject_id, goal?, constraints?, out_of_scope?, open_questions?)` tool — agents currently have no way to update a subproject brief mid-sprint as understanding evolves

*Frontend:*
- Replace the brief textarea with four labeled sections (each independently editable)
- `open_questions` section shown prominently on the subproject view as a checklist the human can resolve

---

### 6. Knowledge Node Staleness

**What**
Add a `status` field to `KnowledgeNode` with values `CURRENT`, `STALE`, `ARCHIVED`. Default `CURRENT`. Context trail scoring deprioritizes non-`CURRENT` nodes; list views filter them out by default.

**Why**
RAW research nodes accumulate over a project's lifetime. There's currently no way to mark a node as superseded without deleting it, which destroys history. Deletion also breaks any `source_refs` pointing to the node from tickets or other nodes.

A status field preserves history while keeping the active knowledge surface clean. It also gives agents a signal: if I'm about to base a decision on a `STALE` node, I should surface that to the human rather than proceeding silently.

**What's required**

*Backend:*
- Add `status` enum to `KnowledgeNode`: `CURRENT`, `STALE`, `ARCHIVED`
- Default `CURRENT` on create
- `PATCH /knowledge/{id}` accepts `status` updates
- `list_knowledge_nodes` and context-trail scoring both filter to `CURRENT` by default; accept `?include_stale=true` query param for full history
- When a node is marked `STALE`, optionally accept a `superseded_by` node ID (foreign key, nullable) so the graph stays connected

*MCP tools:*
- `update_knowledge_node` accepts `status` field
- `list_knowledge_nodes` return output includes status; stale nodes shown with a `[STALE]` prefix so agents don't silently use outdated context

*Frontend:*
- Toggle on knowledge panel to show/hide stale nodes
- Visual treatment (muted/strikethrough) for stale nodes when shown
- "Superseded by" link when `superseded_by` is set

---

## Implementation Priority

| # | Proposal | Value | Effort | Priority |
|---|----------|-------|--------|----------|
| 2 | Knowledge proposal layer | High — closes the trust gap | Medium | **First** |
| 1 | Session checkpointing | High — enables real handoffs | Medium | **Second** |
| 4 | Structured blocker taxonomy | High — immediate triage value | Low | **Third** |
| 3 | Ticket ↔ knowledge linkage | Medium — enables traceability | Low | **Fourth** |
| 6 | Knowledge node staleness | Medium — prevents drift | Low | **Fifth** |
| 5 | Structured subproject brief | Medium — improves reliability | High | **Sixth** |

The proposal layer (#2) and session checkpointing (#1) are the highest-leverage changes because they directly address the core gap: making agent contributions survivable across sessions and reviewable by the human. The others are incremental quality improvements that compound on top of that foundation.
