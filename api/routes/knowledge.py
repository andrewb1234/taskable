"""Knowledge-tree endpoints.

The knowledge tree sits *upstream* of subprojects and tickets: it is where
agents persist raw research, compressed summaries, and drafted PRD/TDD
artifacts before breaking work down into actionable tickets.

Mirrors the existing routing conventions:

* UI-side CRUD is unauthenticated (localhost only), per the decision in
  ``learnings.md`` — every mutation emits an SSE event so the React tree
  view reconciles live.
* An agent-flattened outline lives under ``/agent/*`` and requires the
  bearer token (see ``api.routes.agent``).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.events import Event, get_broadcaster
from api.models.entities import KnowledgeNode, Project
from api.models.enums import ActorRole, KnowledgeNodeStatus, SSEAction
from api.schemas import (
    KnowledgeNodeCreate,
    KnowledgeNodeRead,
    KnowledgeNodeUpdate,
    ContextTrailRead,
)
from api.utils.context_trails import build_context_trail
from api.utils.time import utcnow

router = APIRouter(tags=["knowledge"])


def _require_project(session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _require_node(session, node_id: int) -> KnowledgeNode:
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found.")
    return node


def _infer_actor(request: Request) -> ActorRole:
    """Detect whether the caller is the agent (API key) or the UI (cookie).

    Uses the auth_method set by get_current_user: 'api_key' = AGENT,
    'cookie' = HUMAN. Falls back to HUMAN if unset.
    """
    if getattr(request.state, "auth_method", None) == "api_key":
        return ActorRole.AGENT
    return ActorRole.HUMAN


def _validate_parent(
    session,
    project_id: int,
    parent_id: int | None,
    *,
    self_id: int | None = None,
) -> None:
    """Reject parent references that cross projects or form a cycle."""
    if parent_id is None:
        return
    parent = session.get(KnowledgeNode, parent_id)
    if parent is None:
        raise HTTPException(status_code=400, detail="Parent node does not exist.")
    if parent.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail="Parent node belongs to a different project.",
        )
    # Cycle guard: walk up the ancestor chain, refusing if we hit ``self_id``.
    if self_id is not None:
        cursor = parent
        while cursor is not None:
            if cursor.id == self_id:
                raise HTTPException(
                    status_code=400,
                    detail="parent_id would create a cycle in the knowledge tree.",
                )
            cursor = (
                session.get(KnowledgeNode, cursor.parent_id)
                if cursor.parent_id is not None
                else None
            )


# ---- UI-side CRUD --------------------------------------------------------


@router.get(
    "/projects/{project_id}/knowledge",
    response_model=list[KnowledgeNodeRead],
)
def list_knowledge_nodes(
    project_id: int,
    session: SessionDep,
    include_stale: bool = Query(default=False),
) -> list[KnowledgeNode]:
    """Return knowledge nodes for a project.

    By default only ``CURRENT`` nodes are returned. Pass ``?include_stale=true``
    to include ``STALE`` and ``ARCHIVED`` nodes (for full history).
    The shape is intentionally flat; the client reconstructs the tree
    locally using ``parent_id``. This keeps the endpoint cheap (one query)
    and SSE-friendly (a single action invalidates the whole panel).
    """
    _require_project(session, project_id)
    query = (
        select(KnowledgeNode)
        .where(KnowledgeNode.project_id == project_id)
        .order_by(KnowledgeNode.created_at, KnowledgeNode.id)
    )
    if not include_stale:
        query = query.where(KnowledgeNode.status == KnowledgeNodeStatus.CURRENT)  # type: ignore[union-attr]
    return list(session.exec(query).all())


@router.get(
    "/projects/{project_id}/knowledge/context-trail",
    response_model=ContextTrailRead,
)
def get_context_trail(
    project_id: int,
    session: SessionDep,
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=6, ge=1, le=12),
    include_stale: bool = Query(default=False),
) -> ContextTrailRead:
    """Find the most relevant knowledge branches for a task-intent query."""
    project = _require_project(session, project_id)
    stmt = (
        select(KnowledgeNode)
        .where(KnowledgeNode.project_id == project_id)
        .order_by(KnowledgeNode.created_at, KnowledgeNode.id)
    )
    if not include_stale:
        stmt = stmt.where(KnowledgeNode.status == KnowledgeNodeStatus.CURRENT)
    nodes = list(session.exec(stmt).all())
    return build_context_trail(project, nodes, query, limit=limit)


@router.post(
    "/projects/{project_id}/knowledge",
    response_model=KnowledgeNodeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_node(
    project_id: int,
    payload: KnowledgeNodeCreate,
    session: SessionDep,
    request: Request,
) -> KnowledgeNode:
    _require_project(session, project_id)
    _validate_parent(session, project_id, payload.parent_id)

    actor = _infer_actor(request)
    node = KnowledgeNode(
        project_id=project_id,
        parent_id=payload.parent_id,
        title=payload.title,
        node_type=payload.node_type,
        content=payload.content,
        source_refs=list(payload.source_refs),
        created_by=actor,
    )
    session.add(node)
    session.commit()
    session.refresh(node)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.KNOWLEDGE_NODE_CREATED,
            entity="knowledge_node",
            entity_id=node.id,  # type: ignore[arg-type]
            parent_id=project_id,
        )
    )
    return node


@router.get("/knowledge/{node_id}", response_model=KnowledgeNodeRead)
def get_knowledge_node(node_id: int, session: SessionDep) -> KnowledgeNode:
    return _require_node(session, node_id)


@router.patch("/knowledge/{node_id}", response_model=KnowledgeNodeRead)
async def update_knowledge_node(
    node_id: int,
    payload: KnowledgeNodeUpdate,
    session: SessionDep,
) -> KnowledgeNode:
    node = _require_node(session, node_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update.")

    if "parent_id" in updates:
        _validate_parent(
            session,
            node.project_id,
            updates["parent_id"],
            self_id=node.id,
        )

    for key, value in updates.items():
        setattr(node, key, value)
    node.updated_at = utcnow()

    session.add(node)
    session.commit()
    session.refresh(node)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.KNOWLEDGE_NODE_UPDATED,
            entity="knowledge_node",
            entity_id=node.id,  # type: ignore[arg-type]
            parent_id=node.project_id,
        )
    )
    return node


@router.delete(
    "/knowledge/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_knowledge_node(node_id: int, session: SessionDep) -> None:
    node = _require_node(session, node_id)
    project_id = node.project_id
    session.delete(node)
    session.commit()

    await get_broadcaster().publish(
        Event(
            action=SSEAction.KNOWLEDGE_NODE_DELETED,
            entity="knowledge_node",
            entity_id=node_id,
            parent_id=project_id,
        )
    )
    return None
