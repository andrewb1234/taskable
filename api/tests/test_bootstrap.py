"""Pure bootstrap configuration behavior without installing dependencies."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import bootstrap


def test_old_python_reexecs_with_supported_version(
    monkeypatch,
):
    exec_call: list[object] = []
    monkeypatch.setattr(bootstrap.sys, "version_info", (3, 9))
    monkeypatch.setattr(
        bootstrap,
        "_find_supported_python",
        lambda: "/opt/python3.12",
    )
    monkeypatch.setattr(
        bootstrap.os,
        "execv",
        lambda executable, args: exec_call.extend([executable, args]),
    )

    bootstrap.ensure_supported_python()

    assert exec_call[0] == "/opt/python3.12"
    assert exec_call[1][0] == "/opt/python3.12"
    assert exec_call[1][1] == str(Path(bootstrap.__file__).resolve())


def test_old_python_fails_with_actionable_message(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(bootstrap.sys, "version_info", (3, 9))
    monkeypatch.setattr(bootstrap, "_find_supported_python", lambda: None)

    try:
        bootstrap.ensure_supported_python()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("unsupported Python should stop bootstrap")

    output = capsys.readouterr().out
    assert "Python 3.12 or newer is required" in output
    assert "python3.12 bootstrap.py" in output


def test_supported_python_selection_skips_old_and_current(
    monkeypatch,
):
    paths = {
        "python3.14": "/opt/current",
        "python3.13": "/opt/old",
        "python3.12": "/opt/supported",
    }
    versions = {
        "/opt/old": (3, 11),
        "/opt/supported": (3, 12),
    }
    monkeypatch.setattr(
        bootstrap.shutil,
        "which",
        lambda command: paths.get(command),
    )
    monkeypatch.setattr(
        bootstrap,
        "_probe_python",
        lambda executable: versions.get(executable),
    )

    selected = bootstrap._find_supported_python(
        current_executable="/opt/current",
    )

    assert selected == "/opt/supported"


def test_env_rewrite_removes_legacy_shared_key():
    body = bootstrap._upsert_env_lines(
        [
            "AGENT_API_KEY=legacy-shared-secret",
            "GITHUB_PAT=",
            "JWT_SECRET=old",
        ],
        {
            "JWT_SECRET": "new-secret",
            "LOCAL_AUTH_ENABLED": "true",
        },
        remove={"AGENT_API_KEY"},
    )

    assert "AGENT_API_KEY" not in body
    assert "JWT_SECRET=new-secret" in body
    assert "LOCAL_AUTH_ENABLED=true" in body
    assert "GITHUB_PAT=" in body


def test_secure_atomic_write_is_owner_only(tmp_path):
    target = tmp_path / "nested" / ".env"

    bootstrap._secure_atomic_write(target, "JWT_SECRET=test\n")

    assert target.read_text() == "JWT_SECRET=test\n"
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_windsurf_config_migrates_legacy_shared_secret(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "mcp_config.json"
    target.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "taskable": {
                        "command": "legacy",
                        "env": {
                            "AGENT_API_KEY": "remove-me",
                        },
                    },
                    "unrelated": {"command": "keep-me"},
                }
            }
        )
    )
    credentials_file = tmp_path / "credentials.env"
    monkeypatch.setenv("TASKABLE_WINDSURF_CONFIG", str(target))

    bootstrap.merge_windsurf_config(credentials_file)

    updated = json.loads(target.read_text())
    assert "taskable" not in updated["mcpServers"]
    assert updated["mcpServers"]["unrelated"]["command"] == "keep-me"
    assert updated["mcpServers"]["mouvadah"]["env"] == {
        "TASKABLE_API_URL": "http://localhost:8000/api/v1",
        "TASKABLE_CREDENTIALS_FILE": str(credentials_file),
    }
    assert "remove-me" not in target.read_text()
