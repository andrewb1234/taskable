# Mouvadah Knowledge Index

This directory contains the product, company, security, and technical
specifications for Mouvadah. Read the relevant documents before implementing
or modifying any system component.

## 0. Company and trust source of truth

* `company_blueprint.md`: Positioning, customer, competitors, moat, offerings,
  pricing hypotheses, go-to-market, product architecture, roadmap, and release
  gates.
* `security_and_trust.md`: Verified controls, explicit non-guarantees, threat
  boundaries, findings, target controls, and offering security gates.
* `migrations.md`: Supported database states, backup-before-migrate behavior,
  PostgreSQL deployment gate, failure handling, and rollback policy.
* `recovery.md`: Encrypted database backup, independent object storage,
  restore drills, workspace export, recovery window, and verified purge.
* `incident_response.md`: Telemetry boundaries, alert thresholds, severity,
  response roles, containment, communication, evidence, and drills.

## 1. System Foundations
* `prd.md`: High-level objectives, capabilities, and system architecture.
* `db_schema.md`: SQLite / SQLModel data entities and enumerations.
* `api_endpoints.md`: FastAPI REST routes and Server-Sent Events (SSE) definitions.
* `client_server.md`: Data flow and real-time state synchronization lifecycle.

## 2. Interface Layers
* `frontend.md`: Vite/React component tree, state management, and styling rules.
* `mcp.md`: Model Context Protocol server implementation and tool definitions.

## 3. Operations & Rules
* `testing.md`: Pytest setup, test coverage requirements, and execution rules.
* `deployment.md`: Docker configurations, `.env` schema, and port mapping.
* `folder_navigation.md`: Target directory structure and component locations.
* `protocol.md`: The strict loop for checkpointing, committing, and logging learnings.
