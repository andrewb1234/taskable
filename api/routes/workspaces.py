"""Workspace and membership endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, status
from sqlmodel import select

from api.auth import CurrentUser
from api.authorization import require_workspace
from api.dependencies import SessionDep
from api.models.entities import User, Workspace, WorkspaceMembership
from api.models.enums import WorkspaceRole
from api.schemas import WorkspaceCreate, WorkspaceMemberRead, WorkspaceRead

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:70] or "workspace"


def _available_slug(session, requested: str) -> str:
    slug = requested
    suffix = 2
    while session.exec(select(Workspace.id).where(Workspace.slug == slug)).first():
        slug = f"{requested[:70]}-{suffix}"
        suffix += 1
    return slug


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(
    session: SessionDep,
    user: CurrentUser,
) -> list[WorkspaceRead]:
    rows = session.exec(
        select(Workspace, WorkspaceMembership)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,  # type: ignore[arg-type]
        )
        .where(WorkspaceMembership.user_id == user.id)
        .order_by(Workspace.id)
    ).all()
    return [
        WorkspaceRead(
            id=workspace.id,  # type: ignore[arg-type]
            name=workspace.name,
            slug=workspace.slug,
            role=membership.role,
            created_at=workspace.created_at,
        )
        for workspace, membership in rows
    ]


@router.post(
    "",
    response_model=WorkspaceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    payload: WorkspaceCreate,
    session: SessionDep,
    user: CurrentUser,
) -> WorkspaceRead:
    requested_slug = payload.slug or _slugify(payload.name)
    workspace = Workspace(
        name=payload.name,
        slug=_available_slug(session, requested_slug),
    )
    session.add(workspace)
    session.flush()
    membership = WorkspaceMembership(
        workspace_id=workspace.id,  # type: ignore[arg-type]
        user_id=user.id,  # type: ignore[arg-type]
        role=WorkspaceRole.OWNER,
    )
    session.add(membership)
    session.commit()
    session.refresh(workspace)
    return WorkspaceRead(
        id=workspace.id,  # type: ignore[arg-type]
        name=workspace.name,
        slug=workspace.slug,
        role=membership.role,
        created_at=workspace.created_at,
    )


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberRead])
def list_workspace_members(
    workspace_id: int,
    session: SessionDep,
    user: CurrentUser,
) -> list[WorkspaceMemberRead]:
    require_workspace(session, user, workspace_id, admin=True)
    rows = session.exec(
        select(WorkspaceMembership, User)
        .join(User, WorkspaceMembership.user_id == User.id)  # type: ignore[arg-type]
        .where(WorkspaceMembership.workspace_id == workspace_id)
        .order_by(WorkspaceMembership.id)
    ).all()
    return [
        WorkspaceMemberRead(
            user_id=member.id,  # type: ignore[arg-type]
            email=member.email,
            name=member.name,
            role=membership.role,
            created_at=membership.created_at,
        )
        for membership, member in rows
    ]
