#!/usr/bin/env python3
"""Idempotent demo data loader.

Why this file exists:
    A fresh Taskable install shows an empty UI, which obscures whether SSE /
    drag-and-drop / the modal even work. This script hydrates the database
    with a realistic seed (one game project, one battle-focused subproject,
    tickets across the Kanban columns, threaded comments, and a knowledge tree
    tuned for context trails) so newcomers can click around immediately.

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

SEED_PROJECT_NAME = "BattleForge Context Demo"
DEFAULT_API = os.environ.get("TASKABLE_API_URL", "http://127.0.0.1:8000/api/v1")

TICKETS: list[dict[str, Any]] = [
    {
        "title": "Refactor battle preview component",
        "description": (
            "Use the Battle System context trail before editing the React "
            "preview. Preserve the turn-order and damage-estimate contracts."
        ),
        "status": "TODO",
        "assignee": "AGENT",
    },
    {
        "title": "Confirm damage formula source refs",
        "description": (
            "The human flagged that damage preview may still cite an old "
            "combat math file. Trace the source refs and update the node if stale."
        ),
        "status": "IN_PROGRESS",
        "assignee": "AGENT",
    },
    {
        "title": "Add status-effect ordering tests",
        "description": (
            "Burn, shield, and stun resolution order should be covered before "
            "the next battle tuning pass."
        ),
        "status": "REVIEW",
        "assignee": "AGENT",
    },
    {
        "title": "Write combat UI checkpoint",
        "description": (
            "After the battle preview refactor, save a context checkpoint that "
            "lists which battle nodes were loaded and what changed."
        ),
        "status": "DONE",
        "assignee": "HUMAN",
    },
    {
        "title": "Inventory animation polish",
        "description": "Out of scope for battle work; parked until the UI pass.",
        "status": "DONE",
        "assignee": "HUMAN",
    },
    {
        "title": "Networked battle replay",
        "description": (
            "Blocked until deterministic battle logs are stable enough to replay."
        ),
        "status": "BLOCKED",
        "assignee": "AGENT",
        "blocked_by": "WAITING_DEPENDENCY",
        "blocked_reason": "Waiting for deterministic battle log format to stabilize.",
    },
]

COMMENTS: list[tuple[int, str, str]] = [
    # (ticket_index, author, content)
    (0, "HUMAN", "Start by loading the battle component trail; don't pull the whole game tree."),
    (0, "AGENT", "Loaded Battle System, Combat UI Contract, and Damage Formula nodes."),
    (1, "HUMAN", "Damage preview may still be wrong. I left a correction request in the tree."),
    (5, "HUMAN", "Leave this blocked until the replay format is settled."),
]


def request(method: str, url: str, payload: dict | None = None) -> Any:
    """Tiny wrapper around urllib so this script has zero runtime deps."""
    body = None
    headers = {"Accept": "application/json"}
    api_key = os.environ.get("TASKABLE_API_KEY", os.environ.get("AGENT_API_KEY", ""))
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
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
        {
            "name": SEED_PROJECT_NAME,
            "description": (
                "Game-project seed showing context trails, correction requests, "
                "and checkpoints for an agent working on a battle component."
            ),
        },
    )
    print(f"Created project #{project['id']}: {project['name']}")

    subproject = request(
        "POST",
        f"{api}/projects/{project['id']}/subprojects",
        {
            "name": "Battle Component Pass",
            "context_brief": (
                "Improve the battle preview UI without losing simulation "
                "accuracy. A fresh agent should use the context trail query "
                "`battle component`, load only the relevant battle nodes, and "
                "checkpoint any changed beliefs back into the knowledge tree."
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
            patch: dict[str, Any] = {"status": spec["status"]}
            if spec.get("blocked_by"):
                patch["blocked_by"] = spec["blocked_by"]
            if spec.get("blocked_reason"):
                patch["blocked_reason"] = spec["blocked_reason"]
            ticket = request(
                "PATCH",
                f"{api}/tickets/{ticket['id']}",
                patch,
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

    def create_node(
        title: str,
        node_type: str,
        content: str,
        *,
        parent_id: int | None = None,
        source_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": title,
            "node_type": node_type,
            "content": content,
            "source_refs": source_refs or [],
        }
        if parent_id is not None:
            payload["parent_id"] = parent_id
        node = request(
            "POST",
            f"{api}/projects/{project['id']}/knowledge",
            payload,
        )
        print(f"  knowledge #{node['id']} [{node['node_type']}] {node['title']}")
        return node

    game = create_node(
        "Game architecture signposts",
        "SUMMARY",
        (
            "Use this root when orienting a fresh agent window. The tree is "
            "organized by gameplay subsystem so an agent can walk down from "
            "game-wide context to the specific branch it needs."
        ),
        source_refs=["docs/game/architecture.md"],
    )
    battle = create_node(
        "Battle system",
        "SUMMARY",
        (
            "Use this when working on battle resolution, combat UI, turn order, "
            "damage preview, status effects, or deterministic battle logs. Load "
            "children only as needed; most UI work needs Combat UI Contract and "
            "Damage Formula first."
        ),
        parent_id=game["id"],
        source_refs=["docs/game/battle.md"],
    )
    turn_order = create_node(
        "Turn order rules",
        "RAW",
        (
            "Actors are sorted by speed, then by initiative seed. Stun removes "
            "the actor from the current round after shield reactions resolve. "
            "Summons inherit their owner's initiative bucket."
        ),
        parent_id=battle["id"],
        source_refs=["game/battle/turnOrder.ts"],
    )
    damage = create_node(
        "Damage formula",
        "RAW",
        (
            "Preview damage = max(1, attack - defense) * elementalModifier. "
            "Critical hits apply after shield reduction. The preview UI should "
            "mark estimates when hidden status effects may alter the result."
        ),
        parent_id=battle["id"],
        source_refs=["game/battle/damage.ts", f"node:{turn_order['id']}"],
    )
    status = create_node(
        "Status effect ordering",
        "RAW",
        (
            "Resolution order: shield reactions, stun skips, burn ticks, poison "
            "ticks, regeneration, then round-end cleanup. Human correction: "
            "older notes reversed burn and poison; this node is canonical."
        ),
        parent_id=battle["id"],
        source_refs=["game/battle/statusEffects.ts"],
    )
    combat_ui = create_node(
        "Combat UI contract",
        "SUMMARY",
        (
            "The battle component renders actor queue, selected action, target "
            "preview, and damage estimate. It may read battle selectors but must "
            "not mutate simulation state directly."
        ),
        parent_id=battle["id"],
        source_refs=[f"node:{damage['id']}", f"node:{status['id']}"],
    )
    create_node(
        "Correction request: battle preview stale source",
        "SUMMARY",
        (
            "# Human correction request\n\nThe combat UI node may still imply "
            "damage preview reads from oldCombatMath.ts. Agent should verify "
            "and update the source refs if BattlePreview.tsx is now canonical."
        ),
        parent_id=combat_ui["id"],
        source_refs=[f"node:{combat_ui['id']}", "game/ui/BattlePreview.tsx"],
    )
    create_node(
        "Context checkpoint: battle component handoff",
        "SUMMARY",
        (
            "# Context checkpoint\n\nQuery: battle component\n\n## Loaded nodes\n"
            f"1. node:{battle['id']} Battle system\n"
            f"2. node:{combat_ui['id']} Combat UI contract\n"
            f"3. node:{damage['id']} Damage formula\n\n"
            "## Agent belief to verify\nThe battle preview should show damage "
            "as an estimate when hidden status effects can modify the result."
        ),
        parent_id=combat_ui["id"],
        source_refs=[f"node:{battle['id']}", f"node:{combat_ui['id']}", f"node:{damage['id']}"],
    )
    create_node(
        "Save and replay system",
        "SUMMARY",
        (
            "Use this for save slots, replay logs, and deterministic playback. "
            "Do not load for normal battle UI work unless a ticket mentions replay."
        ),
        parent_id=game["id"],
        source_refs=["game/replay/replayLog.ts"],
    )
    create_node(
        "Inventory and loot UI",
        "SUMMARY",
        (
            "Use this for inventory interactions, loot reveal, and item compare "
            "panels. It is a sibling branch, not battle context."
        ),
        parent_id=game["id"],
        source_refs=["game/ui/InventoryPanel.tsx"],
    )

    # --- Demo: link tickets to knowledge nodes via source_refs ---
    for t_idx, node_ref in [
        (0, f"node:{combat_ui['id']}"),   # Refactor ticket references Combat UI contract
        (1, f"node:{damage['id']}"),       # Damage formula ticket references Damage formula node
        (2, f"node:{status['id']}"),       # Status effect ticket references Status effect ordering
    ]:
        request(
            "PATCH",
            f"{api}/tickets/{ticket_ids[t_idx]}",
            {"source_refs": [node_ref]},
        )
        print(f"  linked ticket #{ticket_ids[t_idx]} → {node_ref}")

    # --- Demo: stale node (old combat math, superseded by damage node) ---
    old_damage = create_node(
        "Damage formula (OLD — superseded)",
        "RAW",
        (
            "DEPRECATED: attack - defense without elemental modifier. This was "
            "used before the elemental system was added. See Damage formula node "
            "for the current formula."
        ),
        parent_id=battle["id"],
        source_refs=["game/battle/oldCombatMath.ts"],
    )
    request(
        "PATCH",
        f"{api}/knowledge/{old_damage['id']}",
        {"status": "STALE", "superseded_by": damage["id"]},
    )
    print(f"  marked node #{old_damage['id']} as STALE (superseded by #{damage['id']})")

    # --- Demo: agent session with handoff note ---
    session_resp = request(
        "POST",
        f"{api}/projects/{project['id']}/sessions",
        {
            "intent": "Refactor battle preview component and confirm damage formula source refs.",
            "loaded_node_ids": [battle["id"], combat_ui["id"], damage["id"]],
        },
    )
    print(f"  created session #{session_resp['id']}: ACTIVE")
    request(
        "PATCH",
        f"{api}/agent/sessions/{session_resp['id']}",
        {
            "handoff_note": (
                "Completed battle preview refactor. Damage formula node source "
                "refs confirmed as canonical (game/battle/damage.ts). "
                "Status effect ordering tests still need coverage (ticket #3). "
                "Replay ticket remains blocked on deterministic log format."
            ),
            "status": "COMPLETE",
        },
    )
    print(f"  closed session #{session_resp['id']}: COMPLETE")

    # A second interrupted session to show the INTERRUPTED indicator
    interrupted = request(
        "POST",
        f"{api}/projects/{project['id']}/sessions",
        {
            "intent": "Investigate networked battle replay log format and unblock ticket.",
            "loaded_node_ids": [battle["id"]],
        },
    )
    request(
        "PATCH",
        f"{api}/agent/sessions/{interrupted['id']}",
        {
            "handoff_note": (
                "Context loaded but ran out of tokens before reaching the replay "
                "log spec. Next agent should start from Save and replay system node."
            ),
            "status": "INTERRUPTED",
        },
    )
    print(f"  created+interrupted session #{interrupted['id']}: INTERRUPTED")

    # --- Demo: pending knowledge proposal on the damage formula node ---
    proposal = request(
        "POST",
        f"{api}/knowledge/{damage['id']}/proposals",
        {
            "proposed_changes": {
                "content": (
                    "Preview damage = max(1, attack - defense) * elementalModifier "
                    "* critMultiplier. Critical hits apply BEFORE shield reduction "
                    "(verified in game/battle/damage.ts line 47). The preview UI "
                    "should mark estimates when hidden status effects may alter the result."
                ),
                "source_refs": [
                    "game/battle/damage.ts",
                    f"node:{turn_order['id']}",
                    "game/battle/damage.ts#L47",
                ],
            },
            "rationale": (
                "Critical hit order was ambiguous in the previous version. "
                "Line 47 of damage.ts confirms crits apply before shield reduction. "
                "Proposing this update for human review before accepting."
            ),
        },
    )
    print(f"  created proposal #{proposal['id']} on node #{damage['id']} (PENDING)")

    return {"project": project, "subproject": subproject, "tickets": ticket_ids}


def reset(api: str) -> None:
    existing = find_project(api, SEED_PROJECT_NAME)
    if not existing:
        print("Nothing to reset.")
        return
    request("DELETE", f"{api}/projects/{existing['id']}")
    print(f"Deleted seed project #{existing['id']}: {existing['name']}")


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
                    f"Open the Taskable web UI and pick '{SEED_PROJECT_NAME}' "
                    "from the sidebar to try context trails, checkpoints, and SSE."
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
