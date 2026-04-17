#!/usr/bin/env python3
"""Idempotent demo data loader.

Why this file exists:
    A fresh Taskable install shows an empty UI, which obscures whether SSE /
    drag-and-drop / the modal even work. This script hydrates the database
    with a realistic seed (one project, one subproject, six tickets across
    all five Kanban columns, two conversations) so newcomers can click around
    immediately. It is also the fixture that the Playwright ``realtime.spec``
    depends on.

Behavior:
    * Checks whether a project named ``SEED_PROJECT_NAME`` already exists.
      If so, prints its URL and exits without mutating anything.
    * Otherwise, creates project → subproject → tickets → comments in a single
      pass against the REST API. No direct DB access, so the same script
      works against a locally-running uvicorn, a docker-compose stack, or a
      remote deployment.

Usage:
    python3 scripts/seed_demo.py                 # seed localhost:8000
    python3 scripts/seed_demo.py --api URL       # alternate endpoint
    python3 scripts/seed_demo.py --reset         # wipe seed-tagged rows first
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
import json
from typing import Any

SEED_PROJECT_NAME = "Taskable Demo"
DEFAULT_API = os.environ.get("TASKABLE_API_URL", "http://127.0.0.1:8000/api/v1")

TICKETS: list[dict[str, Any]] = [
    {
        "title": "Wire SSE into Kanban board",
        "description": (
            "When an agent moves a ticket, the human's board should update "
            "within one second without a reload. Verified by the Playwright "
            "realtime spec."
        ),
        "status": "TODO",
        "assignee": "HUMAN",
    },
    {
        "title": "Add `/agent/context` flattener",
        "description": (
            "LLM-optimized plain-text payload for the MCP "
            "`read_subproject_context` tool."
        ),
        "status": "IN_PROGRESS",
        "assignee": "AGENT",
    },
    {
        "title": "Dockerize the full stack",
        "description": (
            "Two-stage `Dockerfile.web` plus a uvicorn container plus a "
            "docker-compose bind mount at `~/.taskable/`."
        ),
        "status": "REVIEW",
        "assignee": "AGENT",
    },
    {
        "title": "Audit ledger in ticket modal",
        "description": "Surface the last 8 audit entries in the sidebar.",
        "status": "DONE",
        "assignee": "HUMAN",
    },
    {
        "title": "SSE heartbeat tuning",
        "description": "Emit a comment line every 15s to keep proxies happy.",
        "status": "DONE",
        "assignee": "HUMAN",
    },
    {
        "title": "GitHub MR auto-branch (stretch)",
        "description": (
            "`POST /tickets/{id}/mr` currently only attaches; generate a "
            "branch + draft MR when `GITHUB_PAT` is set."
        ),
        "status": "BLOCKED",
        "assignee": "AGENT",
    },
]

COMMENTS: list[tuple[int, str, str]] = [
    # (ticket_index, author, content)
    (1, "HUMAN", "Can you take this one? I'll review the PR."),
    (1, "AGENT", "On it. Starting with the useSSE hook contract."),
    (5, "HUMAN", "Will revisit once we have a real GITHUB_PAT in .env."),
]


def request(method: str, url: str, payload: dict | None = None) -> Any:
    """Tiny wrapper around urllib so this script has zero runtime deps."""
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            return json.loads(data) if data else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url} → HTTP {exc.code}: {body}") from exc


def find_project(api: str, name: str) -> dict | None:
    for project in request("GET", f"{api}/projects") or []:
        if project["name"] == name:
            return project
    return None


def seed(api: str) -> dict[str, Any]:
    existing = find_project(api, SEED_PROJECT_NAME)
    if existing:
        print(f"Project '{SEED_PROJECT_NAME}' already exists (id={existing['id']}); skipping.")
        return {"project": existing, "created": False}

    project = request(
        "POST",
        f"{api}/projects",
        {"name": SEED_PROJECT_NAME, "description": "Seeded by scripts/seed_demo.py"},
    )
    print(f"Created project #{project['id']}: {project['name']}")

    subproject = request(
        "POST",
        f"{api}/projects/{project['id']}/subprojects",
        {
            "name": "Sprint 1 · MVP",
            "context_brief": (
                "Ship the Kanban + MCP surface by end of week. Backend "
                "routes are green; UI polish + docker remain. Agent should "
                "focus on SSE wiring and the docker bind mount."
            ),
        },
    )
    print(f"Created subproject #{subproject['id']}: {subproject['name']}")

    ticket_ids: list[int] = []
    for spec in TICKETS:
        ticket = request(
            "POST",
            f"{api}/subprojects/{subproject['id']}/tickets",
            {
                "title": spec["title"],
                "description": spec["description"],
                "assignee": spec["assignee"],
            },
        )
        # Create tickets in TODO then move to the desired status so the audit
        # ledger reflects the transition (matches real-world usage).
        if spec["status"] != "TODO":
            ticket = request(
                "PATCH",
                f"{api}/tickets/{ticket['id']}",
                {"status": spec["status"]},
            )
        ticket_ids.append(ticket["id"])
        print(f"  + #{ticket['id']} [{ticket['status']}/{ticket['assignee']}] {ticket['title']}")

    for idx, author, body in COMMENTS:
        target_id = ticket_ids[idx]
        comment = request(
            "POST",
            f"{api}/tickets/{target_id}/comments",
            {"author": author, "content": body},
        )
        print(f"    comment #{comment['id']} from {author} on ticket #{target_id}")

    return {"project": project, "subproject": subproject, "tickets": ticket_ids}


def reset(api: str) -> None:
    existing = find_project(api, SEED_PROJECT_NAME)
    if not existing:
        print("Nothing to reset.")
        return
    # The API deliberately does not expose project deletion to guard against
    # accidental loss. For a full reset users can remove
    # ~/.taskable/taskable.db. Be explicit about that here.
    print(
        "Cannot delete via API for safety reasons. "
        "To wipe: stop uvicorn, then `rm ~/.taskable/taskable.db` "
        "and let the app recreate it on next startup."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api",
        default=DEFAULT_API,
        help=f"API base URL (default: {DEFAULT_API})",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Print instructions for clearing the seed project (destructive action left to the user).",
    )
    args = parser.parse_args()

    print(f"→ target: {args.api}")
    try:
        if args.reset:
            reset(args.api)
        else:
            result = seed(args.api)
            if result.get("created", True):
                print()
                print(
                    f"Open http://localhost:5173 and pick '{SEED_PROJECT_NAME}' "
                    "from the sidebar to try drag-and-drop + SSE."
                )
    except urllib.error.URLError as exc:
        print(f"ERROR: cannot reach {args.api}. Is uvicorn running?\n{exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
