# Codebase Navigation Guide

## Directory Structure
* `/api`: FastAPI backend.
  * `/api/models`: SQLModel schemas and enums.
  * `/api/routes`: REST endpoints & SSE broadcaster logic.
  * `main.py`: Uvicorn execution entry point.
* `/web`: React + Vite frontend.
  * `/src/components`: UI elements (shadcn/ui implementations).
  * `/src/hooks`: Custom hooks (e.g., `useSSE` for real-time sync).
  * `App.tsx`: Main routing and layout wrapper.
* `/mcp`: Agent interaction layer.
  * `mcp_server.py`: Python SDK implementation and mapped tool definitions.
* `/docker`: Container configuration.
  * Contains `docker-compose.yml`, `Dockerfile.api`, and `Dockerfile.web`.

## Local Execution Commands
* **Backend:** `cd api && uvicorn main:app --reload`
* **Frontend:** `cd web && npm run dev`
* **Agent Server:** `python mcp/mcp_server.py`

## Development Constraints
* **Single Source of Truth:** The API dictates all data structures. Never duplicate business logic in the frontend or MCP layer.
* **Type Safety:** Ensure Python type hints in FastAPI strictly parallel the TypeScript interfaces in the Vite client.
