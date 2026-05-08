"""Agent session lifecycle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.events import Event, get_broadcaster
from api.models.entities import AgentSession, Project
from api.models.enums import SSEAction
from api.schemas import AgentSessionCreate, AgentSessionRead, AgentSessionUpdate
from api.utils.time import utcnow

router = APIRouter(tags=["sessions"])


def _get_project_or_404(session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _get_session_or_404(session, session_id: int) -> AgentSession:
    agent_session = session.get(AgentSession, session_id)
    if agent_session is None:
        raise HTTPException(status_code=404, detail="Agent session not found.")
    return agent_session


@router.post(
    "/projects/{project_id}/sessions",
    response_model=AgentSessionRead,
    status_code=status.HTTP_201_CREATED,
)
async def start_session(
    project_id: int,
    payload: AgentSessionCreate,
    session: SessionDep,
) -> AgentSession:
    """Start a new agent session, recording intent and initial loaded nodes."""
    _get_project_or_404(session, project_id)

    agent_session = AgentSession(
        project_id=project_id,
        intent=payload.intent,
        loaded_node_ids=list(payload.loaded_node_ids),
        status="ACTIVE",
    )
    session.add(agent_session)
    session.commit()
    session.refresh(agent_session)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.SESSION_STARTED,
            entity="agent_session",
            entity_id=agent_session.id,  # type: ignore[arg-type]
            parent_id=project_id,
        )
    )
    return agent_session


@router.get(
    "/projects/{project_id}/sessions",
    response_model=list[AgentSessionRead],
)
def list_sessions(project_id: int, session: SessionDep) -> list[AgentSession]:
    """Return all sessions for a project, most recent first."""
    _get_project_or_404(session, project_id)
    return list(
        session.exec(
            select(AgentSession)
            .where(AgentSession.project_id == project_id)
            .order_by(AgentSession.started_at.desc())  # type: ignore[union-attr]
        ).all()
    )


@router.patch(
    "/agent/sessions/{session_id}",
    response_model=AgentSessionRead,
)
async def update_session(
    session_id: int,
    payload: AgentSessionUpdate,
    session: SessionDep,
) -> AgentSession:
    """Checkpoint or close an agent session."""
    agent_session = _get_session_or_404(session, session_id)
    updates = payload.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(agent_session, key, value)

    if payload.status in ("COMPLETE", "INTERRUPTED") and agent_session.ended_at is None:
        agent_session.ended_at = utcnow()

    session.add(agent_session)
    session.commit()
    session.refresh(agent_session)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.SESSION_ENDED,
            entity="agent_session",
            entity_id=session_id,
            parent_id=agent_session.project_id,
        )
    )
    return agent_session


@router.get(
    "/agent/sessions/{session_id}",
    response_model=AgentSessionRead,
)
def get_session(session_id: int, session: SessionDep) -> AgentSession:
    return _get_session_or_404(session, session_id)
