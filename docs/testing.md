# API Testing Specification

## Objective
Establish an automated test suite for the FastAPI backend to verify core logic, data models, and agent-facing endpoints before frontend integration.

## Dependencies
* `pytest` (Test runner)
* `pytest-asyncio` (Async support)
* `httpx` (Async test client)

## Test Environment Setup
* Override the database engine in tests to use an **in-memory SQLite database** (`sqlite:///:memory:`).
* Apply `SQLModel.metadata.create_all()` before tests and `drop_all()` afterward to ensure completely isolated test states.

## Required Test Coverage
1. **CRUD Validation:** Verify project creation, subproject assignment, and ticket generation.
2. **State Transitions:** Test the `PATCH /tickets/{id}` endpoint. Ensure invalid status updates return appropriate `400 Bad Request` HTTP errors.
3. **Agent Capabilities:** Mock the `GITHUB_PAT` and test the MR linking logic. Verify the `GET /agent/context/{id}` payload correctly flattens the subproject context into an LLM-readable string.
4. **SSE Broadcasting:** Intercept the internal event broadcaster to ensure state mutations (like ticket updates) successfully trigger internal event payloads.

## Execution
Run `pytest api/tests/ -v` from the repository root. All tests MUST pass before proceeding to frontend implementation.
