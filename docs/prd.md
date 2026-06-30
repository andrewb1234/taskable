# Product Requirements Document: Co-Pilot Workspace

## Objective
A local-first, self-hosted task management system designed for synchronous collaboration between a human developer and an AI agent. It acts as a shared state machine for project execution.

## System Architecture
* **Backend Core:** FastAPI (Python) with SQLModel.
* **Database:** SQLite (persistent local file).
* **Human Interface:** React (Vite) Single Page Application.
* **Agent Interface:** Model Context Protocol (MCP) Server (Python).
* **State Synchronization:** Server-Sent Events (SSE) for one-way real-time UI updates.
* **Infrastructure:** Docker & Docker Compose.

## Core Data Entities
* **Project:** Top-level container.
* **Subproject:** Contextual sprint containing a goal-oriented brief.
* **Ticket:** Actionable unit containing `status`, `description`, `assignee` (Human|Agent), and `mr_link`.
* **Comment:** Threaded discussion attached to tickets.
* **AuditLog:** Immutable ledger of state changes.
* **KnowledgeNode:** Project-scoped context tree for RAW research, SUMMARY compression, and drafted PRD/TDD artifacts upstream of tickets.

## Primary Capabilities
1. **Dual Read/Write:** Both Human UI and Agent MCP can fully execute CRUD operations on all entities.
2. **Contextual Awareness:** Agents can query subproject briefs to understand overarching goals before executing tasks.
3. **Automated Linkage:** Agents can autonomously attach external Git Merge Request URLs to tickets.
4. **Real-time Reflection:** Backend state mutations immediately broadcast to the Human UI via SSE.
5. **Breadcrumbed Planning:** Humans and agents maintain source-referenced knowledge nodes so PRDs, TDDs, and tickets can be traced back to raw context.
6. **Contextual Memory Loading:** Agents can search the knowledge tree by task intent, receive a scoped load order, checkpoint what they loaded, and leave human-correctable context updates.
