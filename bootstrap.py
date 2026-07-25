#!/usr/bin/env python3
"""Authenticated local setup for a fresh Mouvadah clone.

The bootstrap path never disables authentication. It installs the local
runtime, writes a loopback-only development configuration, provisions a local
owner plus a revocable per-user API key, and configures Windsurf MCP (when
present) to read that key from an owner-only credentials file.

Run from the repository root::

    python3 bootstrap.py
"""

from __future__ import annotations

import getpass
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
VENV_DIR = REPO_ROOT / ".venv"
ENV_FILE = REPO_ROOT / ".env"
API_REQ = REPO_ROOT / "api" / "requirements.txt"
MCP_DIR = REPO_ROOT / "mcp"
MCP_SERVER = MCP_DIR / "mcp_server.py"
WEB_DIR = REPO_ROOT / "web"
DEFAULT_CREDENTIALS_FILE = (
    Path.home() / ".config" / "mouvadah" / "credentials.env"
)
DEFAULT_WINDSURF_CONFIG = (
    Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
)
MIN_PYTHON = (3, 12)
PYTHON_CANDIDATES = (
    "python3.15",
    "python3.14",
    "python3.13",
    "python3.12",
)

COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_DIM = "\033[2m"


def log(icon: str, message: str, color: str = "") -> None:
    print(f"{color}{icon}  {message}{COLOR_RESET}")


def ok(message: str) -> None:
    log("✓", message, COLOR_GREEN)


def warn(message: str) -> None:
    log("!", message, COLOR_YELLOW)


def fatal(message: str) -> None:
    log("✗", message, COLOR_RED)
    raise SystemExit(1)


def step(title: str) -> None:
    print()
    print(f"\033[1m── {title} ──{COLOR_RESET}")


def _probe_python(executable: str) -> tuple[int, int] | None:
    """Return an interpreter's major/minor version without importing the app."""
    try:
        result = subprocess.run(
            [
                executable,
                "-c",
                (
                    "import sys; "
                    "print(f'{sys.version_info.major}.{sys.version_info.minor}')"
                ),
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        major, minor = result.stdout.strip().split(".", 1)
        return int(major), int(minor)
    except (OSError, subprocess.SubprocessError, TypeError, ValueError):
        return None


def _find_supported_python(
    *,
    current_executable: str | None = None,
) -> str | None:
    """Find a supported versioned Python when ``python3`` is too old."""
    current = os.path.realpath(current_executable or sys.executable)
    for command in PYTHON_CANDIDATES:
        candidate = shutil.which(command)
        if candidate is None or os.path.realpath(candidate) == current:
            continue
        if (_probe_python(candidate) or (0, 0)) >= MIN_PYTHON:
            return candidate
    return None


def ensure_supported_python() -> None:
    """Re-exec with a supported local Python or fail with actionable guidance."""
    current_version = sys.version_info[:2]
    if current_version >= MIN_PYTHON:
        return

    replacement = _find_supported_python()
    required = ".".join(str(part) for part in MIN_PYTHON)
    current = ".".join(str(part) for part in current_version)
    if replacement is not None:
        warn(
            f"Python {current} is too old; restarting setup with {replacement}."
        )
        os.execv(
            replacement,
            [
                replacement,
                str(Path(__file__).resolve()),
                *sys.argv[1:],
            ],
        )
        return

    fatal(
        f"Python {required} or newer is required (found {current}). "
        "Install a supported Python, then run `python3.12 bootstrap.py` "
        "or a newer versioned command."
    )


def venv_python() -> Path:
    """Return the virtualenv interpreter path for the current platform."""
    return VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "python"


def _secure_atomic_write(path: Path, content: str) -> None:
    """Write a local configuration atomically with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        if os.name == "posix":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        if os.name == "posix":
            path.chmod(0o600)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def ensure_venv() -> None:
    step("Python runtime")
    if VENV_DIR.exists():
        ok(f"Reusing {VENV_DIR}")
    else:
        log("…", "Creating .venv")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
        ok(f"Created {VENV_DIR}")

    python = venv_python()
    log("…", "Installing API dependencies")
    subprocess.check_call(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--quiet",
            "--disable-pip-version-check",
            "-r",
            str(API_REQ),
        ]
    )
    log("…", "Installing the MCP server")
    subprocess.check_call(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--quiet",
            "--disable-pip-version-check",
            "-e",
            str(MCP_DIR),
        ]
    )
    ok("Python and MCP dependencies installed")


def ensure_frontend() -> None:
    step("Web runtime")
    npm = shutil.which("npm")
    if npm is None:
        fatal(
            "npm is required to run the local UI. Install Node.js 20 or newer "
            "and re-run bootstrap.py."
        )
    subprocess.check_call(
        [npm, "ci", "--no-fund", "--no-audit"],
        cwd=WEB_DIR,
    )
    ok("Frontend dependencies installed from package-lock.json")


def _parse_env_file(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return lines, values


def _upsert_env_lines(
    lines: list[str],
    updates: dict[str, str],
    *,
    remove: set[str],
) -> str:
    output: list[str] = []
    handled: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(line)
            continue
        key = stripped.split("=", 1)[0]
        if key in remove:
            continue
        if key in updates:
            if key not in handled:
                output.append(f"{key}={updates[key]}")
                handled.add(key)
            continue
        output.append(line)

    if output and output[-1] != "":
        output.append("")
    if not lines:
        output.extend(
            [
                "# Local Mouvadah configuration generated by bootstrap.py.",
                "# This file is owner-only and must never be committed.",
            ]
        )
    for key, value in updates.items():
        if key not in handled:
            output.append(f"{key}={value}")
    return "\n".join(output).rstrip() + "\n"


def write_local_env(credentials_file: Path) -> None:
    step("Authenticated local configuration")
    lines, values = _parse_env_file(ENV_FILE)
    jwt_secret = values.get("JWT_SECRET", "")
    if jwt_secret in {"", "change-me-to-a-random-string", "dev-jwt-secret-change-me"}:
        jwt_secret = secrets.token_urlsafe(48)
    elif len(jwt_secret) < 32:
        warn("Existing JWT_SECRET was too short and has been rotated.")
        jwt_secret = secrets.token_urlsafe(48)

    body = _upsert_env_lines(
        lines,
        {
            "LOCAL_AUTH_ENABLED": "true",
            "JWT_SECRET": jwt_secret,
            "FRONTEND_URL": "http://localhost:5173",
            "MIGRATION_MODE": "upgrade",
            "VITE_API_URL": "http://localhost:8000/api/v1",
            "TASKABLE_CREDENTIALS_FILE": str(credentials_file),
        },
        remove={"AGENT_API_KEY"},
    )
    _secure_atomic_write(ENV_FILE, body)
    ok(f"Wrote loopback-only {ENV_FILE} with mode 0600")


def prompt_identity() -> tuple[str, str]:
    step("Local owner")
    default_name = getpass.getuser().replace(".", " ").title() or "Local Owner"
    name = input(f"Display name [{default_name}]: ").strip() or default_name
    default_email = f"{getpass.getuser()}@localhost.invalid"
    email = input(f"Owner email [{default_email}]: ").strip() or default_email
    return email, name


def provision_local_owner(
    *,
    email: str,
    name: str,
    credentials_file: Path,
) -> None:
    step("Owner, workspace, and API key")
    subprocess.check_call(
        [
            str(venv_python()),
            "-m",
            "api.local_setup",
            "--email",
            email,
            "--name",
            name,
            "--credentials-file",
            str(credentials_file),
        ],
        cwd=REPO_ROOT,
    )
    ok("Authenticated local owner is ready")


def resolve_mcp_command() -> dict[str, Any]:
    """Choose the most durable installed invocation for the MCP server."""
    global_tool = shutil.which("taskable-mcp")
    venv_tool = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "taskable-mcp"
    if global_tool:
        return {"command": "taskable-mcp", "args": []}
    if venv_tool.exists():
        return {"command": str(venv_tool), "args": []}
    return {
        "command": str(venv_python()),
        "args": [str(MCP_SERVER)],
    }


def _locate_windsurf_config() -> Path | None:
    override = os.environ.get("TASKABLE_WINDSURF_CONFIG")
    if override:
        return Path(override).expanduser()
    candidates = [
        DEFAULT_WINDSURF_CONFIG,
        Path.home() / ".windsurf" / "mcp_config.json",
        Path.home()
        / "Library"
        / "Application Support"
        / "Windsurf"
        / "mcp_config.json",
    ]
    return next(
        (candidate for candidate in candidates if candidate.parent.is_dir()),
        None,
    )


def merge_windsurf_config(credentials_file: Path) -> Path | None:
    step("MCP client")
    target = _locate_windsurf_config()
    if target is None:
        warn(
            "Windsurf was not detected. Use mcp/mcp.json.example with "
            f"TASKABLE_CREDENTIALS_FILE={credentials_file} in another client."
        )
        return None

    current: dict[str, Any] = {}
    if target.exists() and target.stat().st_size:
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            backup = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, backup)
            warn(f"Backed up invalid JSON to {backup}: {exc}")

    command = resolve_mcp_command()
    servers = current.setdefault("mcpServers", {})
    # Migrate the legacy bootstrap entry so a stale shared credential is not
    # left active beside the authenticated Mouvadah configuration.
    servers.pop("taskable", None)
    servers["mouvadah"] = {
        **command,
        "env": {
            "TASKABLE_API_URL": "http://localhost:8000/api/v1",
            "TASKABLE_CREDENTIALS_FILE": str(credentials_file),
        },
    }
    _secure_atomic_write(target, json.dumps(current, indent=2) + "\n")
    ok(f"Configured Mouvadah MCP in {target} with mode 0600")
    return target


def print_summary(
    *,
    credentials_file: Path,
    mcp_config: Path | None,
) -> None:
    step("Ready")
    print("Start the bare-metal stack:")
    print(f"  {COLOR_DIM}make dev{COLOR_RESET}")
    print()
    print("Then:")
    print("  1. Open http://localhost:5173")
    print(f"  2. Copy TASKABLE_API_KEY from {credentials_file}")
    print("  3. Paste it into “Local API key” and choose Continue locally")
    if mcp_config:
        print("  4. Restart Windsurf and run the Mouvadah get_all_projects tool")
    else:
        print(
            "  4. Configure your MCP client from mcp/mcp.json.example, "
            "restart it, and run get_all_projects"
        )
    print()
    print("Docker uses the same owner and database:")
    print(
        f"  {COLOR_DIM}docker compose -f docker/docker-compose.yml "
        f"up --build{COLOR_RESET}"
    )
    print("  UI: http://localhost:3000  API: http://localhost:8000")
    print()
    print(
        "Re-running bootstrap is idempotent. To rotate the local MCP key, run "
        f"`{venv_python()} -m api.local_setup --rotate-key "
        f"--email <email> --name <name>`."
    )


def main() -> int:
    ensure_supported_python()
    print("\033[1mMouvadah authenticated local setup\033[0m")
    print(f"Repository: {REPO_ROOT}")
    if not API_REQ.exists():
        fatal(f"Missing {API_REQ}; run bootstrap.py from a complete clone.")

    credentials_file = Path(
        os.getenv("TASKABLE_CREDENTIALS_FILE", DEFAULT_CREDENTIALS_FILE)
    ).expanduser()
    ensure_venv()
    ensure_frontend()
    email, name = prompt_identity()
    write_local_env(credentials_file)
    provision_local_owner(
        email=email,
        name=name,
        credentials_file=credentials_file,
    )
    mcp_config = merge_windsurf_config(credentials_file)
    print_summary(
        credentials_file=credentials_file,
        mcp_config=mcp_config,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
