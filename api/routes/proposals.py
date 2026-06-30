"""Knowledge proposal endpoints — agent submits, human reviews."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.events import Event, get_broadcaster
from api.models.entities import KnowledgeNode, KnowledgeProposal
from api.models.enums import SSEAction
from api.schemas import (
    KnowledgeProposalCreate,
    KnowledgeProposalRead,
    KnowledgeProposalReview,
)
from api.utils.time import utcnow

router = APIRouter(tags=["proposals"])


def _get_node_or_404(session, node_id: int) -> KnowledgeNode:
    node = session.get(KnowledgeNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found.")
    return node


def _get_proposal_or_404(session, proposal_id: int) -> KnowledgeProposal:
    proposal = session.get(KnowledgeProposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    return proposal


@router.post(
    "/knowledge/{node_id}/proposals",
    response_model=KnowledgeProposalRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_proposal(
    node_id: int,
    payload: KnowledgeProposalCreate,
    session: SessionDep,
) -> KnowledgeProposal:
    """Agent submits a proposed change for human review."""
    node = _get_node_or_404(session, node_id)

    proposal = KnowledgeProposal(
        node_id=node_id,
        proposed_by="AGENT",
        proposed_changes=payload.proposed_changes,
        rationale=payload.rationale,
        status="PENDING",
    )
    session.add(proposal)
    session.commit()
    session.refresh(proposal)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.KNOWLEDGE_PROPOSAL_CREATED,
            entity="knowledge_proposal",
            entity_id=proposal.id,  # type: ignore[arg-type]
            parent_id=node.project_id,
        )
    )
    return proposal


@router.get(
    "/projects/{project_id}/knowledge/proposals",
    response_model=list[KnowledgeProposalRead],
)
def list_proposals(
    project_id: int,
    session: SessionDep,
) -> list[KnowledgeProposal]:
    """List all pending proposals for a project."""
    nodes = list(
        session.exec(
            select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
        ).all()
    )
    node_ids = [n.id for n in nodes]
    if not node_ids:
        return []
    return list(
        session.exec(
            select(KnowledgeProposal)
            .where(KnowledgeProposal.node_id.in_(node_ids))  # type: ignore[union-attr]
            .order_by(KnowledgeProposal.created_at)
        ).all()
    )


@router.get(
    "/knowledge/{node_id}/proposals",
    response_model=list[KnowledgeProposalRead],
)
def list_node_proposals(node_id: int, session: SessionDep) -> list[KnowledgeProposal]:
    """List proposals for a specific node."""
    _get_node_or_404(session, node_id)
    return list(
        session.exec(
            select(KnowledgeProposal)
            .where(KnowledgeProposal.node_id == node_id)
            .order_by(KnowledgeProposal.created_at)
        ).all()
    )


@router.patch(
    "/knowledge/proposals/{proposal_id}",
    response_model=KnowledgeProposalRead,
)
async def review_proposal(
    proposal_id: int,
    payload: KnowledgeProposalReview,
    session: SessionDep,
) -> KnowledgeProposal:
    """Human accepts or rejects a proposal. Accepting applies the patch."""
    if payload.action not in ("accept", "reject"):
        raise HTTPException(status_code=422, detail="action must be 'accept' or 'reject'.")

    proposal = _get_proposal_or_404(session, proposal_id)
    if proposal.status != "PENDING":
        raise HTTPException(status_code=409, detail="Proposal is already reviewed.")

    proposal.status = "ACCEPTED" if payload.action == "accept" else "REJECTED"
    proposal.reviewed_by = payload.reviewed_by
    proposal.reviewed_at = utcnow()

    if payload.action == "accept":
        node = _get_node_or_404(session, proposal.node_id)
        allowed_fields = {"title", "node_type", "status", "content", "source_refs", "parent_id", "superseded_by"}
        for key, value in proposal.proposed_changes.items():
            if key in allowed_fields:
                if key == "parent_id" and value is not None:
                    from api.routes.knowledge import _validate_parent
                    _validate_parent(session, node.project_id, value, self_id=node.id)
                setattr(node, key, value)
        from api.utils.time import utcnow as _utcnow
        node.updated_at = _utcnow()
        session.add(node)

    session.add(proposal)
    session.commit()
    session.refresh(proposal)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.KNOWLEDGE_PROPOSAL_REVIEWED,
            entity="knowledge_proposal",
            entity_id=proposal_id,
            parent_id=proposal.node_id,
        )
    )
    return proposal
