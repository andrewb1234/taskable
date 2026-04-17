"""Single source of truth for the API version string.

Kept in its own module so docker healthchecks and JSON responses don't have to
reach into ``main.py`` or ``pyproject.toml`` at runtime.
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

__version__ = "0.1.0"


@lru_cache(maxsize=1)
def git_sha() -> str | None:
    """Return the short git SHA of the running codebase, if available.

    Resolution order:
        1. ``TASKABLE_GIT_SHA`` env var (set by Docker build args / CI).
        2. ``git rev-parse --short HEAD`` against the repo root.
        3. ``None`` when neither option works (e.g. shipped wheel).
    """
    env_value = os.environ.get("TASKABLE_GIT_SHA")
    if env_value:
        return env_value.strip() or None

    repo_root = Path(__file__).resolve().parent.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    sha = result.stdout.strip()
    return sha or None
