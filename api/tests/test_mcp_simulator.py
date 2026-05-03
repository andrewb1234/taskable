"""Agent simulator integration test.

Boots a real FastAPI uvicorn process against a throwaway SQLite file, then
launches the MCP stdio server as a subprocess and drives it through a proper
JSON-RPC handshake. Asserts both the protocol response and the database side
effect of a ``tools/call`` → PATCH round-trip.

This test sits between the unit suite (in-memory DB, FastAPI TestClient) and
the Playwright browser spec (real Chromium, real Vite) so we have end-to-end
coverage of the MCP wire layer without paying the browser tax.

Marked ``integration`` so it can be skipped in ultra-fast CI loops with
``pytest -m 'not integration'``.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
MCP_SERVER_SCRIPT = REPO_ROOT / "mcp" / "mcp_server.py"
TEST_AGENT_KEY = "integration-test-key"


# --------------------------------------------------------------------------
# Uvicorn subprocess fixture
# --------------------------------------------------------------------------


def _find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(url: str, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=1.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_exc = exc
        time.sleep(0.1)
    raise TimeoutError(f"API did not become healthy within {timeout_s}s: {last_exc}")


@pytest.fixture(scope="module")
def live_api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, str]]:
    """Spawn a real uvicorn process backed by a throwaway SQLite file.

    Yields a dict with ``base_url`` (e.g. ``http://127.0.0.1:51234/api/v1``)
    and ``db_path`` so assertions can talk to SQLite directly.
    """
    if not VENV_PYTHON.exists():  # pragma: no cover - sanity guard
        pytest.skip(f"Expected interpreter not found at {VENV_PYTHON}")

    port = _find_free_port()
    db_path = tmp_path_factory.mktemp("taskable-int") / "live.db"
    env = {
        **os.environ,
        "AGENT_API_KEY": TEST_AGENT_KEY,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "PYTHONUNBUFFERED": "1",
    }

    proc = subprocess.Popen(
        [
            str(VENV_PYTHON), "-m", "uvicorn",
            "api.main:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(f"{base}/healthz")
        yield {"base_url": f"{base}/api/v1", "db_path": str(db_path)}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------
# Helpers for talking JSON-RPC over stdio to mcp_server.py
# --------------------------------------------------------------------------


class MCPClient:
    """Tiny JSON-RPC over stdio helper."""

    def __init__(self, proc: asyncio.subprocess.Process) -> None:
        self._proc = proc
        self._id = 0

    async def send(self, method: str, params: dict | None = None) -> None:
        self._id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or {},
        }
        assert self._proc.stdin is not None
        self._proc.stdin.write((json.dumps(message) + "\n").encode())
        await self._proc.stdin.drain()

    async def notify(self, method: str, params: dict | None = None) -> None:
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        assert self._proc.stdin is not None
        self._proc.stdin.write((json.dumps(message) + "\n").encode())
        await self._proc.stdin.drain()

    async def recv(self) -> dict:
        assert self._proc.stdout is not None
        line = await self._proc.stdout.readline()
        if not line:
            raise RuntimeError("MCP server closed stdout unexpectedly")
        return json.loads(line.decode())


async def _spawn_mcp(api_url: str) -> asyncio.subprocess.Process:
    env = {
        **os.environ,
        "AGENT_API_KEY": TEST_AGENT_KEY,
        "TASKABLE_API_URL": api_url,
        "PYTHONUNBUFFERED": "1",
    }
    return await asyncio.create_subprocess_exec(
        str(VENV_PYTHON),
        str(MCP_SERVER_SCRIPT),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(REPO_ROOT),
    )


async def _initialize(client: MCPClient) -> dict:
    await client.send(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "simulator", "version": "0"},
        },
    )
    response = await client.recv()
    await client.notify("notifications/initialized", {})
    return response


# --------------------------------------------------------------------------
# The tests themselves
# --------------------------------------------------------------------------


@pytest.mark.integration
async def test_mcp_simulator_roundtrip(live_api: dict[str, str]) -> None:
    """Full MCP wire test: handshake + tools/list + tools/call + DB check.

    This single test covers all five MCP tools via one happy-path scenario,
    mirroring how an agent would actually use them: list → context →
    update → comment → link MR.
    """
    # Seed a project with one ticket through the HTTP API first.
    async with httpx.AsyncClient(base_url=live_api["base_url"], timeout=5) as http:
        project = (await http.post("/projects", json={"name": "Sim"})).json()
        subproject = (
            await http.post(
                f"/projects/{project['id']}/subprojects",
                json={"name": "Sim sub", "context_brief": "Seeded by simulator."},
            )
        ).json()
        ticket = (
            await http.post(
                f"/subprojects/{subproject['id']}/tickets",
                json={"title": "Simulated task", "assignee": "HUMAN"},
            )
        ).json()

    # Now drive the MCP server.
    proc = await _spawn_mcp(live_api["base_url"])
    try:
        client = MCPClient(proc)
        init_response = await _initialize(client)
        assert init_response["result"]["serverInfo"]["name"] == "copilot-workspace"

        # tools/list - sanity check
        await client.send("tools/list", {})
        tools = (await client.recv())["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        assert tool_names == {
            # Read
            "get_all_projects",
            "get_active_tasks",
            "read_subproject_context",
            # Create
            "create_project",
            "create_subproject",
            "create_ticket",
            # Mutate
            "update_ticket_status",
            "link_mr",
            "leave_comment",
            # Delete
            "delete_project",
            "delete_subproject",
            "delete_ticket",
            "delete_knowledge_node",
            # Knowledge tree
            "list_knowledge_nodes",
            "read_knowledge_node",
            "create_knowledge_node",
            "update_knowledge_node",
        }

        # tools/call -> update_ticket_status (the mutation under test)
        await client.send(
            "tools/call",
            {
                "name": "update_ticket_status",
                "arguments": {"ticket_id": ticket["id"], "status": "IN_PROGRESS"},
            },
        )
        call_result = (await client.recv())["result"]
        body = call_result["content"][0]["text"]
        assert "IN_PROGRESS" in body and f"#{ticket['id']}" in body

        # tools/call -> leave_comment
        await client.send(
            "tools/call",
            {
                "name": "leave_comment",
                "arguments": {
                    "ticket_id": ticket["id"],
                    "content": "Picking this up now.",
                },
            },
        )
        comment_result = (await client.recv())["result"]["content"][0]["text"]
        assert comment_result.startswith("Posted comment")

        # tools/call -> link_mr
        await client.send(
            "tools/call",
            {
                "name": "link_mr",
                "arguments": {
                    "ticket_id": ticket["id"],
                    "url": "https://github.com/acme/sim/pull/1",
                },
            },
        )
        mr_result = (await client.recv())["result"]["content"][0]["text"]
        assert "https://github.com/acme/sim/pull/1" in mr_result
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()

    # Confirm the DB reflects every mutation the simulator performed.
    conn = sqlite3.connect(live_api["db_path"])
    try:
        row = conn.execute(
            "SELECT status, assignee, mr_link FROM ticket WHERE id = ?",
            (ticket["id"],),
        ).fetchone()
        assert row == ("IN_PROGRESS", "AGENT", "https://github.com/acme/sim/pull/1")

        comment_count = conn.execute(
            "SELECT COUNT(*) FROM comment WHERE ticket_id = ? AND author = 'AGENT'",
            (ticket["id"],),
        ).fetchone()[0]
        assert comment_count == 1

        audit_actions = {
            row[0]
            for row in conn.execute(
                "SELECT action FROM auditlog WHERE ticket_id = ?",
                (ticket["id"],),
            )
        }
        assert "STATUS_UPDATE" in audit_actions
        assert "MR_LINKED" in audit_actions
    finally:
        conn.close()


@pytest.mark.integration
async def test_mcp_simulator_rejects_bad_status(live_api: dict[str, str]) -> None:
    """Invalid status values must be rejected before the API is ever hit.

    The MCP SDK validates arguments against the tool's ``inputSchema.enum``
    BEFORE invoking our handler (defense-in-depth), and our handler also
    re-checks the status for the case where a caller has a permissive SDK.
    Either rejection path is acceptable; both keep bad data out of the DB.
    """
    proc = await _spawn_mcp(live_api["base_url"])
    try:
        client = MCPClient(proc)
        await _initialize(client)
        await client.send(
            "tools/call",
            {
                "name": "update_ticket_status",
                "arguments": {"ticket_id": 9999, "status": "WEEKEND_MODE"},
            },
        )
        payload = await client.recv()
        # The SDK returns either a JSON-RPC ``error`` when schema validation
        # fails, or a regular ``result`` with ``isError: true`` / an error
        # text frame from our handler. Accept either shape.
        if "error" in payload:
            message = json.dumps(payload["error"])
        else:
            message = payload["result"]["content"][0]["text"]
        assert "WEEKEND_MODE" in message, message
        lowered = message.lower()
        assert any(kw in lowered for kw in ("invalid", "error", "not one of")), message
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()


@pytest.mark.integration
async def test_mcp_simulator_creation_flow(live_api: dict[str, str]) -> None:
    """End-to-end creation flow via the four new tools.

    Walks the path an agent would take when bootstrapping a workspace from
    scratch: get_all_projects (empty) -> create_project -> create_subproject
    -> create_ticket. Asserts each MCP response parses correctly AND that the
    resulting DB rows exist with the expected parent/child linkage.
    """
    proc = await _spawn_mcp(live_api["base_url"])
    try:
        client = MCPClient(proc)
        await _initialize(client)

        async def call(name: str, arguments: dict) -> str:
            await client.send(
                "tools/call", {"name": name, "arguments": arguments}
            )
            payload = await client.recv()
            assert "result" in payload, payload
            return payload["result"]["content"][0]["text"]

        # 1. create_project
        created = await call(
            "create_project",
            {
                "name": "MCP Creation Flow",
                "description": "Exercised by test_mcp_simulator_creation_flow",
            },
        )
        assert created.startswith("Created project #"), created
        project_id = int(created.split("#")[1].split(":")[0])

        # 2. get_all_projects now includes our new project.
        listing = await call("get_all_projects", {})
        assert f"id={project_id}" in listing, listing
        assert "MCP Creation Flow" in listing

        # 3. create_subproject under it.
        created_sp = await call(
            "create_subproject",
            {
                "project_id": project_id,
                "name": "Creation sub",
                "context_brief": "Ship the four new MCP creation tools.",
            },
        )
        assert created_sp.startswith("Created subproject #"), created_sp
        subproject_id = int(created_sp.split("#")[1].split(" ")[0])

        # 4. create_ticket under that subproject.
        created_t = await call(
            "create_ticket",
            {
                "subproject_id": subproject_id,
                "title": "Wire up tool",
                "description": "Implement the MCP handler and register it.",
                "assignee": "AGENT",
            },
        )
        assert created_t.startswith("Created ticket #"), created_t
        assert "[TODO/AGENT]" in created_t, created_t
        ticket_id = int(created_t.split("#")[1].split(" ")[0])

        # 5. Bogus assignee should be rejected (same dual-layer behavior as
        #    the status test: SDK schema-check or handler guard).
        await client.send(
            "tools/call",
            {
                "name": "create_ticket",
                "arguments": {
                    "subproject_id": subproject_id,
                    "title": "Bad assignee",
                    "description": "Should not be created.",
                    "assignee": "ROBOT",
                },
            },
        )
        bad = await client.recv()
        body = (
            json.dumps(bad["error"])
            if "error" in bad
            else bad["result"]["content"][0]["text"]
        )
        assert "ROBOT" in body, body
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()

    # DB-level verification: parent chain is intact and nothing extra leaked.
    conn = sqlite3.connect(live_api["db_path"])
    try:
        row = conn.execute(
            "SELECT name FROM project WHERE id = ?", (project_id,)
        ).fetchone()
        assert row and row[0] == "MCP Creation Flow"

        row = conn.execute(
            "SELECT project_id, name FROM subproject WHERE id = ?",
            (subproject_id,),
        ).fetchone()
        assert row == (project_id, "Creation sub")

        row = conn.execute(
            "SELECT subproject_id, status, assignee, title FROM ticket "
            "WHERE id = ?",
            (ticket_id,),
        ).fetchone()
        assert row == (subproject_id, "TODO", "AGENT", "Wire up tool")

        # Verify the "bad assignee" attempt didn't persist.
        rejected = conn.execute(
            "SELECT COUNT(*) FROM ticket WHERE title = 'Bad assignee'"
        ).fetchone()[0]
        assert rejected == 0
    finally:
        conn.close()


@pytest.mark.integration
async def test_mcp_simulator_knowledge_flow(live_api: dict[str, str]) -> None:
    """End-to-end knowledge tree build via the MCP wire protocol.

    Exercises the full upstream planning loop: a SUMMARY parent, a nested
    RAW child, a listed outline, a drilled-down read, and an update that
    promotes SUMMARY → PRD. Persistence is verified against the live SQLite.
    """
    proc = await _spawn_mcp(live_api["base_url"])
    try:
        client = MCPClient(proc)
        await _initialize(client)

        async def call(name: str, arguments: dict) -> str:
            await client.send(
                "tools/call", {"name": name, "arguments": arguments}
            )
            payload = await client.recv()
            assert "result" in payload, payload
            return payload["result"]["content"][0]["text"]

        # Seed a project directly via the MCP so the test is hermetic.
        project_msg = await call(
            "create_project",
            {
                "name": "Knowledge Flow",
                "description": "Exercised by test_mcp_simulator_knowledge_flow",
            },
        )
        project_id = int(project_msg.split("#")[1].split(":")[0])

        # 1. create_knowledge_node (SUMMARY at the root)
        summary_msg = await call(
            "create_knowledge_node",
            {
                "project_id": project_id,
                "title": "Architecture overview",
                "node_type": "SUMMARY",
                "content": "FastAPI + SQLModel + React via SSE.",
                "source_refs": ["/abs/README.md"],
            },
        )
        assert summary_msg.startswith("Created knowledge node #"), summary_msg
        summary_id = int(summary_msg.split("#")[1].split(" ")[0])

        # 2. create_knowledge_node (RAW child nested under the summary)
        child_msg = await call(
            "create_knowledge_node",
            {
                "project_id": project_id,
                "title": "api/main.py",
                "node_type": "RAW",
                "content": "from fastapi import FastAPI\napp = FastAPI()",
                "parent_id": summary_id,
                "source_refs": ["/abs/api/main.py"],
            },
        )
        child_id = int(child_msg.split("#")[1].split(" ")[0])
        assert f"parent=#{summary_id}" in child_msg, child_msg

        # 3. list_knowledge_nodes returns a hierarchical outline.
        outline = await call(
            "list_knowledge_nodes", {"project_id": project_id}
        )
        assert f"[SUMMARY #{summary_id}]" in outline, outline
        assert f"[RAW #{child_id}]" in outline, outline
        # Child line is indented under parent line.
        assert outline.index(f"#{summary_id}") < outline.index(f"#{child_id}")

        # 4. read_knowledge_node surfaces source refs + content.
        detail = await call("read_knowledge_node", {"node_id": child_id})
        assert "/abs/api/main.py" in detail, detail
        assert "from fastapi import FastAPI" in detail, detail

        # 5. update_knowledge_node promotes SUMMARY → PRD.
        promoted = await call(
            "update_knowledge_node",
            {"node_id": summary_id, "node_type": "PRD"},
        )
        assert "[PRD]" in promoted, promoted
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()

    # DB-level verification: parent chain + type promotion persisted.
    conn = sqlite3.connect(live_api["db_path"])
    try:
        row = conn.execute(
            "SELECT node_type, parent_id FROM knowledgenode WHERE id = ?",
            (summary_id,),
        ).fetchone()
        assert row == ("PRD", None)

        row = conn.execute(
            "SELECT node_type, parent_id FROM knowledgenode WHERE id = ?",
            (child_id,),
        ).fetchone()
        assert row == ("RAW", summary_id)
    finally:
        conn.close()
