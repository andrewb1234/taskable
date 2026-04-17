# Co-Pilot Workspace: Knowledge Index

This directory contains the strict specifications for the "Taskable" Co-Pilot Workspace. Read the relevant documents before implementing or modifying any system component. 

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
