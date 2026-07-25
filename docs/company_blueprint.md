# Mouvadah Company and Product Blueprint

Status: working company strategy and product source of truth
Audit date: 2026-07-25
Repository: `andrewb1234/taskable`

## Executive decision

Mouvadah should be the **vendor-neutral control and memory plane for human-agent
software delivery**.

It should not lead as:

- another broad project-management suite;
- another coding-agent runtime;
- an AI chatbot layered over a backlog; or
- a generic vector-memory service.

The initial customer is an AI-native engineering team that already uses coding
agents and has discovered that the hard problem is no longer starting an agent.
The hard problem is preserving trustworthy context, dividing work safely,
recovering from failed workers, reviewing agent decisions, and giving humans a
single legible execution record across models and runtimes.

The product promise is:

> Give every human and agent the same durable project state, make parallel work
> safe, and keep every important decision inspectable.

This positioning is narrower than "project management" and broader than a
single agent harness. It creates a credible integration path with Linear, Jira,
GitHub, Codex, Claude Code, Cursor, Devin, and future agents instead of forcing
customers to replace all of them.

## What exists today

The current repository is a functional alpha, not a concept demo.

### Shipped product capabilities

- Shared project, subproject, ticket, comment, and audit state.
- React Kanban interface with targeted real-time refresh over SSE.
- Project-scoped knowledge trees with RAW, SUMMARY, PRD, and TDD node types.
- Deterministic context-trail search that recommends a scoped load order.
- Human correction requests and agent-authored knowledge proposals.
- Agent-session checkpoints and handoff notes.
- Ticket-to-knowledge source references and knowledge-to-ticket backlinks.
- Structured blockers, ticket dependency edges, and dependency-aware readiness.
- Atomic ticket claims, worker identity, leases, heartbeat, and expired-work
  recovery.
- Local stdio MCP server with 22 tools.
- Google authentication, revocable browser sessions, workspace-bound scoped
  API keys, workspace ownership, membership roles, and object authorization.
- SQLite for local use and a nominal PostgreSQL configuration path.
- Docker packaging, 133 passing backend/MCP tests plus a PostgreSQL-only
  migration/claim regression, MCP subprocess simulation, a production
  frontend build, and three Playwright browser tests.

### Current product maturity

| Area | Current stage | Evidence |
|---|---|---|
| Core workflow | Alpha, coherent | Human UI and MCP mutate the same state |
| Agent coordination | Strong alpha | Dependencies, CAS claims, leases, recovery |
| Durable context | Strong alpha | Trees, trails, proposals, sessions, provenance |
| Human governance | Early alpha | Proposal review and audit actions exist |
| Collaboration | Early alpha | Tenant-scoped workspaces and basic roles; no invite or role-management UI |
| Hosted SaaS | Security-gated alpha | Tenancy, migrations, sessions, CSRF/origin, scoped keys, and headers exist; recovery and operations remain |
| Local/self-host | Usable alpha | SQLite, Docker, stdio MCP |
| Enterprise | Not available | No RBAC, SSO/SCIM, policy, compliance, or SLA |

The most important conclusion is that Mouvadah has a differentiated core and a
working application-layer tenant boundary, but the sign-in screen must not
create a false impression of SaaS readiness. Authorization is only one release
gate; browser-session security, delivery controls, recovery, and
operations remain unfinished.

## Customer and problem

### Primary ideal customer profile

Two-to-twenty-person software teams that:

- use two or more coding-agent products or run their own harness;
- delegate multiple implementation tasks per week;
- need a human to remain accountable for scope and quality;
- find issue trackers insufficient for agent memory and recovery; and
- prefer local-first, self-hosted, or clearly isolated cloud data.

Likely early buyers are a technical founder, staff engineer, developer
productivity lead, or AI platform engineer. The end users are engineers,
product engineers, and the agents they operate.

### Secondary customers

- Internal platform teams building agent fleets.
- Consultancies running many parallel client workstreams.
- Regulated or IP-sensitive teams needing a customer-controlled deployment.
- Solo power users who need continuity across Codex, Claude Code, Cursor, and
  local scripts.

### Jobs to be done

1. "When several agents are working, show me exactly who owns what and prevent
   duplicate execution."
2. "When an agent or chat dies, let the next one resume from verified context
   without rereading the whole project."
3. "When an agent changes project knowledge, let me inspect the rationale and
   approve the durable change."
4. "When a task is blocked, distinguish dependency wait, human input, and
   external failure."
5. "When I change agent vendors, preserve project memory and execution state."
6. "When security or management asks what happened, provide a useful audit
   trail rather than reconstructing it from chat logs."

### Anti-ICP

Mouvadah should not initially target large non-technical departments, portfolio
planning, CRM, marketing workflows, or teams that do not delegate meaningful
work to agents. Serving those segments would force premature breadth and put the
company in direct feature competition with Jira, Linear, Plane, Asana, and
Monday.

## Competitive landscape

The comparison is based on public product and pricing material available on the
audit date. Absence of a feature means it was not prominent in the reviewed
official materials, not proof that an internal or newly released equivalent
does not exist.

| Competitor | What it wins on | Current offer | Gap Mouvadah can own |
|---|---|---|---|
| Linear | Best-in-class issue UX, agent delegation, hosted MCP, integrated coding sessions | Free; Basic $10/user/month; Business $16/user/month; usage-priced coding sessions | Agent-neutral durable memory, customer-controlled deployment, explicit worker leases and knowledge review |
| GitHub Copilot | Code, PR, security, and agent mission control inside the system of record | Individual plans from free to $100/user/month; Business $19 and Enterprise $39/user/month | Cross-repository/project knowledge upstream of GitHub issues and runtime-independent orchestration |
| Shortcut + Korey | Software project management plus agent coordination and a product-workflow agent | Shortcut $0/$8.50/$12 per user; Korey $59/$149 per organization | Local-first operation, deterministic project memory, open agent control plane |
| Plane | Broad open-source/self-hosted project management, wiki, intake, many views, low seat price | Free; Pro $6/user/month; Business $13/user/month; enterprise self-hosting | A narrower agent-native workflow with safe claims, leases, handoffs, and reviewable knowledge |
| Atlassian Jira + Rovo | Enterprise distribution, connected knowledge, search, agents, governance | Rovo included in paid Atlassian products; standalone Standard announced at $5/user/month after beta | Lightweight deployment and agent-vendor neutrality for teams that reject the Atlassian suite |
| Devin | End-to-end coding runtime, codebase knowledge, integrations, fleet execution | Free; Pro $20; Max $200; Teams $80 minimum with usage credits | Persistent control state across Devin and non-Devin agents; no model/runtime lock-in |
| Conductor | Excellent local parallel coding-agent UX using isolated worktrees | Local desktop workspace for Claude Code, Codex, and Cursor | Durable multi-project memory and work truth beyond a single machine and git workspace |

### Strategic reading of the market

Linear and GitHub are rapidly absorbing generic "assign an issue to an agent"
functionality. That feature cannot be Mouvadah's moat. Plane makes broad
self-hosted project management inexpensive. Devin and Conductor make starting
and supervising parallel coding sessions increasingly easy.

The durable opening is the **trustworthy state between planning systems and
execution runtimes**:

- context selected by intent rather than whole-workspace dumping;
- provenance and correction rather than opaque retrieval;
- state transitions designed for concurrent machine workers;
- explicit handoffs across short-lived agent sessions;
- human approval at the point where agent output becomes organizational memory;
- deployment and data ownership independent of the agent vendor.

Mouvadah should integrate with incumbents, not require immediate replacement.
The first successful Linear and GitHub integrations should make Mouvadah more
valuable while leaving those systems as the outward team tracker.

## Defensibility and moat

No single alpha feature is a moat. The moat is a compounding system with four
layers.

### 1. Execution graph

Dependencies, readiness, atomic claims, leases, recovery, and audit history
form a reliable machine-work queue that conventional issue trackers usually
treat as integration behavior. As customers run more agents, this graph becomes
the operational history required to improve throughput and reliability.

### 2. Provenance graph

Knowledge nodes, source references, corrections, proposals, sessions, tickets,
and code changes can form a traceable graph from evidence to decision to work to
result. That graph is more defensible than a pile of embeddings because humans
can inspect and correct it.

### 3. Vendor-neutral protocol surface

The same state should work through local stdio MCP, remote authenticated MCP,
REST, SDKs, webhooks, and tracker adapters. Neutrality becomes valuable as
customers change models, IDEs, and coding agents.

### 4. Reliability data and policy

With customer consent and privacy-preserving aggregation, Mouvadah can learn
which task shapes, context loads, dependencies, approval patterns, and handoff
behaviors predict success. The product can eventually recommend safer execution
plans without owning the underlying model.

The moat is weakened if Mouvadah becomes a thin Kanban UI or stores unreviewed,
untraceable summaries. It strengthens every time a completed project leaves a
cleaner, more trustworthy provenance and execution graph.

## Product architecture

### Product layers

1. **Memory:** knowledge nodes, source provenance, staleness, corrections,
   context trails, and checkpoints.
2. **Planning:** subproject briefs, acceptance criteria, tickets, dependencies,
   and readiness.
3. **Coordination:** worker claims, leases, heartbeat, recovery, and
   idempotency.
4. **Governance:** proposals, approvals, actor identity, policy, audit,
   budgets, and destructive-action controls.
5. **Integration:** MCP, REST, SDKs, GitHub/Linear/Jira sync, webhooks, and
   agent-runtime adapters.
6. **Insight:** throughput, blocked time, retry rate, handoff quality,
   acceptance rate, and cost/outcome attribution.

### Stage-appropriate technology target

Keep the modular monolith. Microservices would add operational cost without
improving the current product.

| Layer | Alpha/local | Cloud beta target | Scale trigger |
|---|---|---|---|
| API | FastAPI + SQLModel | Same, with explicit service boundaries | Split only after measured contention |
| Web | React + Vite | Same, route-based product shell | Add SSR only for public marketing/docs |
| Database | SQLite | Managed PostgreSQL + Alembic | Read replicas after real demand |
| Realtime | In-memory SSE | PostgreSQL LISTEN/NOTIFY or a small broker | Dedicated event bus for multi-region |
| Background work | Caller-driven | Durable job table + worker | Queue service after workload proves it |
| Agent protocol | Local stdio MCP | Streamable HTTP MCP + OAuth scopes | Regional gateways when required |
| Files | Local filesystem | S3-compatible object storage | Customer-controlled buckets for enterprise |
| Observability | Health endpoint | Structured logs, traces, errors, metrics | SIEM export and SLO automation |
| Delivery | Manual/Render-style | CI, migrations, preview, staged deploy | Progressive delivery at larger scale |

### Architectural principles

- One durable write path for UI, agents, and integrations.
- Authorization checks on every object lookup, not only route authentication.
- Idempotent commands at all retry-prone boundaries.
- Explicit concurrency semantics; never label read-check-write as atomic.
- Human-legible state before opaque automation.
- Local-first remains a supported product, not a development accident.
- No security or compliance claim without a testable control and evidence.

## Product offerings

Pricing is a launch hypothesis to validate with design partners, not a promise
to publish before billing and entitlements exist.

### Community

Price: free, self-hosted.

- Single-user or trusted local network.
- SQLite, Docker, local stdio MCP.
- Full core knowledge and coordination primitives.
- Community support.
- Clear source license and upgrade path.

Purpose: adoption, trust, integration development, and solo power-user value.

### Cloud

Hypothesis: **$39 per workspace per month**, including three human members;
$8 for each additional member. No agent seats.

- Managed PostgreSQL and backups.
- Hosted web application and remote authenticated MCP.
- Unlimited connected agent identities within fair-use API limits.
- GitHub integration and one external tracker sync.
- Team workspaces, roles, audit history, export, and restore.
- Email support.

Why workspace pricing: Mouvadah does not pay for model inference and should not
tax customers for adding agents. A modest workspace base captures value from
coordination while remaining easy to trial.

### Scale

Hypothesis: **$149 per workspace per month**, including ten human members.

- Multiple projects and tracker connections.
- Approval policies, advanced roles, audit export, webhooks, and usage insight.
- Longer history and configurable retention.
- Priority support and migration assistance.
- Optional metered high-volume event or storage usage.

### Enterprise

Annual contract, starting at a meaningful platform minimum rather than a cheap
seat SKU.

- Customer-managed cloud or supported self-hosting.
- SAML/OIDC SSO, SCIM, group mapping, granular RBAC, policy-as-code.
- Data residency, customer-managed keys where justified, SIEM export.
- Contracted support and availability targets.
- Security package: architecture, subprocessors, DPA, pen-test summary,
  vulnerability management, incident process, and control evidence.

Enterprise must not launch until the security gates in
`docs/security_and_trust.md` are met.

### Services

Short fixed-scope onboarding packages can fund learning without turning the
company into a consultancy:

- agent workflow and tracker integration workshop;
- self-hosted deployment and security review;
- migration of existing project memory and execution history; and
- custom runtime adapter development that feeds the common product.

Any custom work must produce a reusable connector, template, or control.

## Go-to-market

### Beachhead motion

1. Recruit five design partners already running multiple coding agents.
2. Install Community locally in under ten minutes.
3. Connect one live repository and one agent runtime.
4. Measure one complete workflow: plan, claim, execute, review, hand off.
5. Publish evidence-backed case studies about avoided duplicate work, recovery
   time, context-loading time, and human review effort.
6. Convert teams that need shared access, backup, and remote MCP to Cloud.

### Acquisition loops

- Open-source repository and installable MCP package.
- Integration templates for Codex, Claude Code, Cursor, and custom harnesses.
- Public "agent operations" playbooks and failure postmortems.
- GitHub/Linear/Jira marketplace listings after security and sync quality pass.
- Shareable, redacted execution reports that carry the product name.

### Message

Primary:

> Your agents are temporary. Your project memory and execution truth should not
> be.

Supporting:

- Run many agents without duplicate work.
- Resume after any agent or chat stops.
- Review what becomes durable project knowledge.
- Keep your data and switch agent vendors without losing the project.

### What not to claim

- "Autonomous software company."
- "SOC 2 compliant" before an audited program exists.
- "Enterprise secure" while objects are globally visible to authenticated
  users.
- "Exactly once execution"; leases provide safe claiming, not universal
  exactly-once side effects.
- "AI-powered" as the headline; the value is reliable coordination and trust.

## Business mechanics

### Revenue model

- Recurring workspace subscription for hosted collaboration.
- Annual platform contract for enterprise deployment and controls.
- Meter only costs with a real variable driver: storage, high event volume, or
  optional Mouvadah-provided inference.
- Do not meter connected BYO agents or ordinary ticket operations.

### Cost structure

The core control plane should have high gross margin because it does not perform
model inference. Principal variable costs are database, object storage,
realtime connections, logs, support, and optional integration polling.

Before setting final prices, instrument:

- active workspaces and weekly active humans;
- connected agent identities and completed agent sessions;
- database and event cost per active workspace;
- support minutes per workspace;
- storage and retention growth; and
- willingness to pay for backup, collaboration, remote MCP, and governance.

### North-star metric

**Verified agent work units completed per active workspace per week.**

A work unit is verified only when it reaches the configured completion gate
(for example tests passed and human review or merge recorded). Raw agent
messages and ticket creation are not value metrics.

### Supporting metrics

- Median time from ready to claimed.
- Duplicate-claim prevention count.
- Lease expiry and successful recovery rate.
- Median handoff-to-resume time.
- Context-trail precision feedback.
- Knowledge proposal acceptance and correction rate.
- Human review minutes per verified work unit.
- Percentage of tickets with evidence and acceptance criteria.
- Weekly retained workspaces and expansion in active projects.
- Security: authorization-test coverage, restore-test age, patch latency.

## Product gaps and priorities

### P0: safe product foundation

- **Delivered:** workspace/tenant model, membership, project ownership, and
  centralized object-level authorization across application and MCP routes.
- **Delivered:** tenant-scoped SSE and baseline authenticated actor
  classification.
- **Delivered:** trusted OAuth callback origin and production secret
  validation.
- **Delivered:** ordered Alembic migrations, safe adoption of recognized
  legacy schemas, automatic SQLite backup, PostgreSQL upgrade evidence, and
  fail-closed deployment checks.
- **Delivered:** CI for the Python 3.12/3.14 backend, frontend type/build, and
  authenticated realtime path; dependency, secret, and CodeQL scanning;
  SHA-pinned Actions; and Dependabot coverage.
- **Delivered:** exact-Origin cookie-write defense, server-revocable browser
  sessions, workspace/project-scoped API keys, baseline per-process limits,
  and security headers.
- Automate managed PostgreSQL backup/restore and run production-like recovery
  exercises with measured RPO/RTO.
- Add hash-locked Python dependencies, container scanning, SBOMs, artifact
  signing, and build provenance.
- Tenant export, verified deletion, and recovery-window controls.
- License, privacy policy, terms, and a security contact.

### P1: complete team beta

- Hosted remote MCP using the current HTTP authorization specification.
- Workspace onboarding, invitations, and role-management workflows.
- GitHub App with repository/PR linkage and webhook-driven state.
- Idempotent ticket creation and command deduplication.
- Durable multi-instance events and jobs.
- Structured product telemetry, logs, error tracking, and operator runbooks.
- Improved audit records with actor ID and before/after metadata.

### P2: distribution and paid value

- Linear and GitHub Issues bidirectional sync; Jira after demand is proven.
- Policy engine for approval, budgets, destructive actions, and agent scope.
- Execution insights and reliability reports.
- Templates/playbooks for common agent workflows.
- Billing, entitlements, trials, lifecycle email, and in-product upgrade.
- Attachment/evidence storage with scanning and retention.

### P3: enterprise readiness

- SAML/OIDC, SCIM, granular RBAC, service accounts, and group mapping.
- SIEM/audit export, retention policies, legal hold where required.
- Regional/private deployment, encryption-key options, and vendor review.
- Independent penetration test and formal control-evidence program.
- Contracted SLOs only after measured operational performance.

## Release gates

### Community 1.0

- Fresh install in under ten minutes on macOS and Linux.
- Upgrade preserves data; backup and restore are documented and tested.
- Core tests and MCP simulation pass in CI.
- License and security reporting process are explicit.
- No default secret is accepted on a non-loopback deployment.

### Cloud private beta

- Cross-tenant read, write, delete, SSE, and API-key tests pass.
- PostgreSQL migration and production-like restore exercises pass.
- OAuth, CSRF, session, rate-limit, and security-header controls pass review.
- Operator can identify a tenant, revoke access, restore data, and audit a
  destructive action.
- Error monitoring and incident paging are live.

### Paid team availability

- Five design partners complete real weekly workflows.
- At least three would be "very disappointed" to lose the product.
- Median setup time and first verified work unit meet defined targets.
- Billing, entitlements, export, deletion, and support commitments are tested.
- Security posture page distinguishes controls from roadmap without ambiguity.

## Key risks

| Risk | Mitigation |
|---|---|
| Linear/GitHub absorb the category | Stay neutral, local-first, provenance-rich, and integration-led |
| Product becomes another tracker | Make execution reliability and durable memory the primary workflow |
| Knowledge accumulates errors | Proposals, provenance, staleness, correction metrics, and review policy |
| Self-hosting consumes support | One supported deployment path, diagnostics bundle, paid enterprise support |
| Broad enterprise scope stalls product | Gate enterprise work behind design-partner demand and a platform minimum |
| Agent actions cause destructive effects | Least privilege, scoped credentials, approval policy, idempotency, audit |
| Alpha auth creates false confidence | Keep public-SaaS claims blocked until session, CSRF, delivery, recovery, and operations gates are verified |

## Decisions requiring founder validation

These are business-owner decisions, not safe defaults for an implementation
agent:

1. Source license and trademark policy.
2. Whether the first paid motion is hosted Cloud, supported self-hosting, or
   both.
3. Initial design-partner segment and geographic/data-residency constraints.
4. Final prices after interviews and cost instrumentation.
5. Whether Mouvadah will ever provide model inference or remain strictly BYO
   agent/model.
6. Appetite and budget for compliance certifications and enterprise support.

Until those decisions are made, implementation should preserve both local and
hosted paths and avoid legal or compliance claims.

## Research references

- Linear pricing and agent workflows:
  https://linear.app/pricing,
  https://linear.app/docs/agents-in-linear,
  https://linear.app/docs/mcp,
  https://linear.app/docs/ai-credits
- GitHub Copilot plans and agents:
  https://github.com/features/copilot,
  https://github.com/features/copilot/agents,
  https://docs.github.com/en/copilot/concepts/billing/organizations-and-enterprises
- Plane pricing, self-hosting, knowledge, access, and integrations:
  https://plane.so/pricing
- Shortcut agent coordination and pricing:
  https://www.shortcut.com/agents/,
  https://www.shortcut.com/pricing/
- Korey packaging:
  https://korey.ai/pricing/
- Atlassian Rovo packaging:
  https://support.atlassian.com/subscriptions-and-billing/docs/managing-your-bill-for-rovo/
- Devin packaging:
  https://docs.devin.ai/admin/billing/self-serve
- Conductor positioning:
  https://www.conductor.build/
