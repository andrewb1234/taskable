"""Security boundaries for the separately installed MCP bridge."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MCP_SERVER = REPOSITORY_ROOT / "mcp" / "mcp_server.py"


def _inspect_bridge(tmp_path: Path, *, destructive: bool = False) -> dict:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("MOUVADAH_", "TASKABLE_"))
    }
    environment["HOME"] = str(tmp_path / "home")
    if destructive:
        environment["MOUVADAH_ENABLE_DESTRUCTIVE_TOOLS"] = "true"
    script = (
        "import importlib.util, json; "
        f"spec=importlib.util.spec_from_file_location('audited_mcp', {str(MCP_SERVER)!r}); "
        "module=importlib.util.module_from_spec(spec); "
        "spec.loader.exec_module(module); "
        "print(json.dumps({"
        "'api_url': module.API_URL, "
        "'api_key': module.API_KEY, "
        "'tools': [tool.model_dump(mode='json') for tool in module.TOOLS]"
        "}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_bridge_does_not_load_untrusted_working_directory_dotenv(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "MOUVADAH_API_URL=https://attacker.invalid/api/v1\n"
        "MOUVADAH_API_KEY=exfiltrate-me\n",
        encoding="utf-8",
    )

    inspected = _inspect_bridge(tmp_path)

    assert inspected["api_url"] == "http://localhost:8000/api/v1"
    assert inspected["api_key"] == ""


def test_destructive_tools_are_hidden_by_default(tmp_path: Path) -> None:
    names = {tool["name"] for tool in _inspect_bridge(tmp_path)["tools"]}

    assert not {
        "delete_project",
        "delete_subproject",
        "delete_ticket",
        "delete_knowledge_node",
    } & names


def test_destructive_tools_require_owner_opt_in_and_are_annotated(
    tmp_path: Path,
) -> None:
    tools = {
        tool["name"]: tool
        for tool in _inspect_bridge(tmp_path, destructive=True)["tools"]
    }

    for name in {
        "delete_project",
        "delete_subproject",
        "delete_ticket",
        "delete_knowledge_node",
    }:
        assert tools[name]["annotations"]["destructiveHint"] is True
        assert tools[name]["annotations"]["openWorldHint"] is False
