# Observability and Incident Response

This runbook defines Mouvadah's private-beta operating procedure. It is an
internal objective, not a customer SLA. Availability, RPO, and RTO claims stay
unpublished until repeated production evidence supports them.

## Telemetry boundary

The API emits redacted JSON logs to standard error. Every HTTP response gets a
new server-generated `X-Request-ID`; valid W3C `traceparent` headers propagate
through OpenTelemetry spans. Logs contain method, normalized route template,
status, duration, deployment identity, pseudonymous actor IDs when available,
request ID, and trace ID. They do not contain:

- request or response bodies;
- query strings;
- cookies, authorization headers, session IDs, or raw API keys;
- email addresses, client IP addresses, or database statements; or
- exception values or frame local variables.

Unhandled errors may be aggregated in Sentry when `SENTRY_DSN` is configured.
The SDK disables default PII, request bodies, user objects, local variables,
and Sentry transaction sampling; a final scrubber removes headers, cookies,
query strings, credentials, and URL passwords. OpenTelemetry owns tracing so
the tracing backend remains vendor-neutral.

Prometheus metrics are available only at `/internal/metrics` when a dedicated
`METRICS_BEARER_TOKEN` of at least 32 characters is configured. The endpoint
returns `404` while disabled and requires `Authorization: Bearer <token>` when
enabled. Never reuse a user, agent, OAuth, or database credential. Scrapers
must use HTTPS, keep the token in their secret store, and never expose the
endpoint through a public dashboard.

The metrics cover:

- API request count, status, latency, auth/authorization failures, and
  unhandled errors;
- database operation count, latency, errors, and pool connections in use;
- SSE subscribers, invalidation delivery, resyncs, reconnects, and transport
  health; and
- backup, restore, verification, and lifecycle job outcomes and duration.

`/healthz` is the lightweight process liveness check. `/readyz` verifies a
database round trip and rejects traffic with `503` when the database is
unavailable or realtime is degraded/not started. Neither endpoint includes
credentials, tenant data, or infrastructure hostnames.

OTLP trace and transient-job metric export is enabled with
`OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example`. The standard
exporters append `/v1/traces` and `/v1/metrics`. Put collector authentication
in `OTEL_EXPORTER_OTLP_HEADERS`, never in the URL.
Production rejects plaintext export URLs. `OTEL_TRACE_SAMPLE_RATIO` defaults
to `0.1`; a sampled parent remains sampled and an unsampled parent remains
unsampled.

## Required production views and alerts

Build one service dashboard from these signals before calling monitoring
operational:

| Signal | Private-beta alert threshold | Initial severity |
|---|---|---|
| External `/healthz` | Two consecutive failures across two minutes | SEV-2 |
| `/readyz` | Any sustained failure for two minutes | SEV-2 |
| HTTP 5xx ratio | Greater than 5% for five minutes with at least 20 requests | SEV-2 |
| HTTP p95 latency | Greater than 2 seconds for ten minutes | SEV-3 |
| Database errors | Any sustained errors for two minutes | SEV-2 |
| Database p95 latency | Greater than 1 second for ten minutes | SEV-3 |
| Database pool | More than 80% of configured capacity for ten minutes | SEV-3 |
| Realtime health | `mouvadah_realtime_transport_healthy == 0` for two minutes | SEV-2 |
| Realtime publish | Any failures in five minutes | SEV-2 |
| Auth failures | More than 50 per minute for five minutes | Security triage |
| Backup job | Any failed run or no verified success within 26 hours | SEV-2 |
| Restore drill | Missed scheduled exercise | SEV-3 |

These are starting thresholds. Review false positives, traffic volume, and
measured baselines monthly. Do not silently loosen a threshold during an
incident; record the change and rationale.

Render or the chosen hosting provider must also page on crash loops, failed
deployments, memory exhaustion, certificate failures, and backup Cron Job
failure. A dashboard without a tested notification destination is not paging.
Test every paging route quarterly and after ownership changes.

## Severity and roles

- **SEV-1:** suspected cross-workspace disclosure, credential/signing-key
  compromise, destructive unauthorized action, unrecoverable data loss, or a
  broad security incident. Page immediately.
- **SEV-2:** production outage, sustained high errors, database/realtime
  unavailability, failed backup, or severe degradation with no safe
  workaround. Page immediately.
- **SEV-3:** limited degradation, elevated latency, a missed non-urgent
  control, or a defect with a safe workaround. Acknowledge in business hours.
- **SEV-4:** low-risk issue or improvement. Track normally.

Every SEV-1/2 names an incident commander, operations lead, communications
owner, and scribe. One person may hold multiple roles at this stage, but each
responsibility must be explicit. The incident commander owns severity,
priorities, and closure; the scribe owns the timeline and evidence.

## Response procedure

1. Acknowledge the page and create an incident record with start time,
   detector, provisional severity, affected environment, current Git SHA, and
   deployment ID. Never paste secrets or raw customer content.
2. Confirm impact with the external health check, `/readyz`, normalized route
   metrics, recent deploys, database state, realtime health, and failed jobs.
   Use request and trace IDs to correlate logs, errors, and spans.
3. For suspected security or tenant isolation failures, declare SEV-1,
   preserve audit/log evidence, restrict production access, and stop risky
   writes before debugging. Do not test a suspected cross-tenant path with
   real customer data.
4. Contain with the smallest reversible action: pause a rollout, remove a
   bad instance, revoke an API key/session, disable an integration, or switch
   traffic to a verified healthy version. Record who approved every
   destructive or credential action.
5. Roll back application code only when the deployed database schema remains
   compatible with the target commit. Never reverse migrations casually.
   Database restore follows `docs/recovery.md`, requires an isolated target
   first, and retains the pre-restore backup and evidence.
6. Validate recovery from outside the service: health, readiness, login,
   workspace isolation, MCP authentication, one reversible write, realtime
   resync, and any incident-specific invariant.
7. Communicate status at least every 30 minutes for SEV-1 and every 60 minutes
   for SEV-2. State known impact, mitigation, and next update time; do not
   speculate about cause or promise an unmeasured recovery time.
8. Close only after signals stay healthy for an observation window, temporary
   access is removed, evidence is retained, and follow-up owners are assigned.

If production credentials may have been exposed, rotate the affected secret,
revoke sessions/keys derived from it, verify the old value no longer works,
and examine logs and audit events for use. Do not put the old or new value in
the incident record.

## Evidence and communication

Retain, under access control:

- the timestamped incident timeline and decisions;
- request/trace IDs and redacted log queries;
- alert screenshots or exports;
- Git commit, CI evidence, deploy and rollback IDs;
- database migration revision and backup/restore evidence;
- revoked credential identifiers (never values);
- customer-facing messages and recipients; and
- verification results and follow-up tickets.

Security incidents use the private reporting channel in
[`SECURITY.md`](../SECURITY.md).
Potentially affected customers receive a factual notice after scope is
validated and legal/privacy obligations are assessed. Public status text must
distinguish investigation, mitigation, monitoring, and resolution.

## Review and drills

Publish a blameless post-incident review within five business days for every
SEV-1/2. Include impact, detection, timeline, contributing conditions, what
worked, evidence gaps, and corrective tickets with owners and deadlines.
Corrective work belongs in Mouvadah and references the incident evidence.

Exercise these scenarios at least quarterly during private beta:

- database unavailable and safe application rollback;
- lost realtime listener with reconnect/resync;
- leaked agent API key and session revocation;
- failed backup plus isolated restore verification; and
- suspected cross-workspace access.

Measure detection, acknowledgement, containment, and recovery times. RPO and
RTO remain internal observations until repeated production restore exercises
justify a published commitment.
