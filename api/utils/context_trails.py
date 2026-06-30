"""Context-trail search over a project's knowledge tree.

The trail is deliberately heuristic, not embedding-based. Taskable is
local-first and dependency-light, so the first pass should work offline and be
predictable enough for a human to correct when the agent follows the wrong
branch.
"""

from __future__ import annotations

import re
from collections import Counter

from api.models.entities import KnowledgeNode, Project
from api.schemas import (
    ContextTrailChildHint,
    ContextTrailItem,
    ContextTrailRead,
    ContextTrailSegment,
)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "into",
    "of",
    "on",
    "the",
    "to",
    "with",
    "work",
    "working",
}


def _tokens(text: str) -> list[str]:
    found = re.findall(r"[a-z0-9_]+", text.lower())
    return [token for token in found if len(token) > 1 and token not in STOP_WORDS]


def _preview(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _segment(node: KnowledgeNode) -> ContextTrailSegment:
    return ContextTrailSegment(
        id=node.id or 0,
        title=node.title,
        node_type=node.node_type,
    )


def _child_hint(node: KnowledgeNode) -> ContextTrailChildHint:
    return ContextTrailChildHint(
        id=node.id or 0,
        title=node.title,
        node_type=node.node_type,
        content_preview=_preview(node.content, 140),
        source_refs=list(node.source_refs),
    )


def _path_for(
    node: KnowledgeNode, by_id: dict[int, KnowledgeNode]
) -> list[ContextTrailSegment]:
    path: list[KnowledgeNode] = []
    seen: set[int] = set()
    cursor: KnowledgeNode | None = node
    while cursor is not None and cursor.id is not None and cursor.id not in seen:
        seen.add(cursor.id)
        path.append(cursor)
        cursor = by_id.get(cursor.parent_id) if cursor.parent_id is not None else None
    return [_segment(item) for item in reversed(path)]


def _score_node(node: KnowledgeNode, query_terms: list[str]) -> tuple[int, list[str], str]:
    title = node.title.lower()
    content = node.content.lower()
    refs = " ".join(node.source_refs).lower()
    matched: list[str] = []
    buckets: Counter[str] = Counter()
    score = 0

    for term in query_terms:
        if term in title:
            score += 8
            matched.append(term)
            buckets["title"] += 1
        if term in refs:
            score += 5
            matched.append(term)
            buckets["source refs"] += 1
        occurrences = content.count(term)
        if occurrences:
            score += min(occurrences, 4) * 2
            matched.append(term)
            buckets["content"] += 1

    if matched and node.node_type.value in {"SUMMARY", "PRD", "TDD"}:
        score += 2

    unique_matched = sorted(set(matched), key=matched.index)
    if not unique_matched:
        return 0, [], "No query terms matched."

    locations = ", ".join(name for name, _ in buckets.most_common())
    reason = f"Matched {', '.join(unique_matched)} in {locations}."
    return score, unique_matched, reason


def build_context_trail(
    project: Project,
    nodes: list[KnowledgeNode],
    query: str,
    *,
    limit: int = 6,
) -> ContextTrailRead:
    """Return the ranked branches and load order for a task-intent query."""

    by_id = {node.id: node for node in nodes if node.id is not None}
    children: dict[int | None, list[KnowledgeNode]] = {}
    for node in nodes:
        children.setdefault(node.parent_id, []).append(node)
    for sibling_list in children.values():
        sibling_list.sort(key=lambda n: (n.created_at, n.id or 0))

    query_terms = _tokens(query)
    ranked: list[tuple[int, KnowledgeNode, list[str], str]] = []
    if query_terms:
        for node in nodes:
            score, matched_terms, reason = _score_node(node, query_terms)
            if score > 0:
                ranked.append((score, node, matched_terms, reason))
    else:
        for node in children.get(None, [])[:limit]:
            ranked.append((1, node, [], "Root node suggested because the query is empty."))

    ranked.sort(key=lambda item: (-item[0], item[1].created_at, item[1].id or 0))

    items: list[ContextTrailItem] = []
    load_order: list[ContextTrailSegment] = []
    loaded_ids: set[int] = set()

    for score, node, matched_terms, reason in ranked[: max(1, min(limit, 12))]:
        path = _path_for(node, by_id)
        for segment in path:
            if segment.id not in loaded_ids:
                load_order.append(segment)
                loaded_ids.add(segment.id)

        direct_children = children.get(node.id, [])[:4]
        items.append(
            ContextTrailItem(
                id=node.id or 0,
                title=node.title,
                node_type=node.node_type,
                parent_id=node.parent_id,
                path=path,
                score=score,
                matched_terms=matched_terms,
                reason=reason,
                content_preview=_preview(node.content),
                source_refs=list(node.source_refs),
                child_count=len(children.get(node.id, [])),
                children=[_child_hint(child) for child in direct_children],
            )
        )

    return ContextTrailRead(
        project_id=project.id or 0,
        project_name=project.name,
        query=query,
        load_order=load_order,
        items=items,
    )


def format_context_trail_markdown(trail: ContextTrailRead) -> str:
    """Render a context trail as compact markdown for MCP/agent use."""

    lines: list[str] = [
        f"# Context trail for project #{trail.project_id}: {trail.project_name}",
        f"Query: {trail.query.strip() or '(empty)'}",
        "",
        "## Suggested load order",
    ]

    if not trail.load_order:
        lines.append("(no matching knowledge nodes)")
    else:
        for index, segment in enumerate(trail.load_order, start=1):
            lines.append(
                f"{index}. [{segment.node_type.value} #{segment.id}] {segment.title}"
            )

    lines.append("")
    lines.append("## Matched branches")
    if not trail.items:
        lines.append(
            "No branch matched this query. Call list_knowledge_nodes to inspect "
            "the full tree, or create/update nodes with clearer signpost text."
        )
    for item in trail.items:
        path = " > ".join(f"{part.title} (#{part.id})" for part in item.path)
        lines.append("")
        lines.append(f"### [{item.node_type.value} #{item.id}] {item.title}")
        lines.append(f"Path: {path}")
        lines.append(f"Reason: {item.reason}")
        if item.source_refs:
            lines.append("Source refs: " + ", ".join(item.source_refs[:4]))
        if item.content_preview:
            lines.append("Preview: " + item.content_preview)
        if item.children:
            lines.append("Children to drill into next:")
            for child in item.children:
                lines.append(
                    f"- [{child.node_type.value} #{child.id}] {child.title}"
                )

    lines.append("")
    lines.append(
        "Checkpoint pattern: after loading these nodes, create a SUMMARY child "
        "with source_refs like node:<id> for each loaded node, recording what "
        "you believed and what changed."
    )
    return "\n".join(lines)
