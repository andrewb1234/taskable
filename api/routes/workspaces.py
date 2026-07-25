"""Workspace and membership endpoints."""

from __future__ import annotations

import re
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import select

from api.auth import CurrentUser
from api.config import get_settings
from api.authorization import require_workspace
from api.dependencies import SessionDep
from api.models.entities import (
    ApiKey,
    User,
    Workspace,
    WorkspaceLifecycleEvent,
    WorkspaceMembership,
)
from api.models.enums import WorkspaceLifecycleAction, WorkspaceRole
from api.schemas import (
    WorkspaceCreate,
    WorkspaceDeletionCreate,
    WorkspaceDeletionRead,
    WorkspaceLifecycleEventRead,
    WorkspaceMemberRead,
    WorkspaceRead,
)
from api.security import get_api_key_authorization
from api.utils.time import utcnow
from api.workspace_export import build_workspace_export

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
    query = (
        select(Workspace, WorkspaceMembership)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,  # type: ignore[arg-type]
        )
        .where(WorkspaceMembership.user_id == user.id)
        .order_by(Workspace.id)
    )
    api_key = get_api_key_authorization()
    if api_key is not None:
        query = query.where(Workspace.id == api_key.workspace_id)
    rows = session.exec(query).all()
    return [
        WorkspaceRead(
            id=workspace.id,  # type: ignore[arg-type]
            name=workspace.name,
            slug=workspace.slug,
            role=membership.role,
            created_at=workspace.created_at,
            deletion_requested_at=workspace.deletion_requested_at,
            purge_after=workspace.purge_after,
            deletion_requested_by=workspace.deletion_requested_by,
            deletion_export_sha256=workspace.deletion_export_sha256,
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
    if get_api_key_authorization() is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace-bound API keys cannot create workspaces.",
        )
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
        deletion_requested_at=workspace.deletion_requested_at,
        purge_after=workspace.purge_after,
        deletion_requested_by=workspace.deletion_requested_by,
        deletion_export_sha256=workspace.deletion_export_sha256,
    )


def _require_owner_browser(
    session: SessionDep,
    user: CurrentUser,
    workspace_id: int,
    *,
    include_deleted: bool = False,
    lock: bool = False,
) -> tuple[Workspace, WorkspaceMembership]:
    if get_api_key_authorization() is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Workspace export and deletion controls require an "
                "interactive owner session."
            ),
        )
    workspace, membership = require_workspace(
        session,
        user,
        workspace_id,
        admin=True,
        include_deleted=include_deleted,
        lock=lock,
    )
    if WorkspaceRole(membership.role) != WorkspaceRole.OWNER:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return workspace, membership


@router.get("/{workspace_id}/export")
def export_workspace(
    workspace_id: int,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    workspace, _ = _require_owner_browser(
        session,
        user,
        workspace_id,
        lock=True,
    )
    content, sha256, counts = build_workspace_export(session, workspace)
    event = WorkspaceLifecycleEvent(
        workspace_id=workspace_id,
        action=WorkspaceLifecycleAction.EXPORTED,
        actor_user_id=user.id,
        details={
            "sha256": sha256,
            "record_counts": counts,
            "format": "mouvadah.workspace-export.v1",
        },
    )
    session.add(event)
    session.commit()
    date_stamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f'attachment; filename="mouvadah-{workspace.slug}-'
                f'{date_stamp}.json"'
            ),
            "X-Mouvadah-Export-SHA256": sha256,
        },
    )


@router.post(
    "/{workspace_id}/deletion",
    response_model=WorkspaceDeletionRead,
)
def schedule_workspace_deletion(
    workspace_id: int,
    payload: WorkspaceDeletionCreate,
    session: SessionDep,
    user: CurrentUser,
) -> WorkspaceDeletionRead:
    workspace, _ = _require_owner_browser(
        session,
        user,
        workspace_id,
        lock=True,
    )
    if payload.confirmation != workspace.slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Type the exact workspace slug to confirm deletion.",
        )

    recent_exports = list(
        session.exec(
            select(WorkspaceLifecycleEvent)
            .where(
                WorkspaceLifecycleEvent.workspace_id == workspace_id,
                WorkspaceLifecycleEvent.action
                == WorkspaceLifecycleAction.EXPORTED,
            )
            .order_by(WorkspaceLifecycleEvent.id.desc())
            .limit(20)
        ).all()
    )
    now = utcnow()
    matching_export = next(
        (
            event
            for event in recent_exports
            if event.details.get("sha256") == payload.export_sha256
            and event.occurred_at >= now - timedelta(hours=24)
        ),
        None,
    )
    if matching_export is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Create a fresh workspace export before scheduling deletion."
            ),
        )

    purge_after = now + timedelta(
        days=get_settings().deletion_recovery_days
    )
    workspace.deletion_requested_at = now
    workspace.purge_after = purge_after
    workspace.deletion_requested_by = user.id
    workspace.deletion_export_sha256 = payload.export_sha256
    session.add(workspace)

    api_keys = list(
        session.exec(
            select(ApiKey).where(
                ApiKey.workspace_id == workspace_id,
                ApiKey.revoked.is_(False),
            )
        ).all()
    )
    for api_key in api_keys:
        api_key.revoked = True
        session.add(api_key)

    session.add(
        WorkspaceLifecycleEvent(
            workspace_id=workspace_id,
            action=WorkspaceLifecycleAction.DELETION_SCHEDULED,
            actor_user_id=user.id,
            details={
                "export_sha256": payload.export_sha256,
                "purge_after": f"{purge_after.isoformat()}Z",
                "revoked_api_keys": len(api_keys),
            },
        )
    )
    session.commit()
    return WorkspaceDeletionRead(
        workspace_id=workspace_id,
        deletion_requested_at=now,
        purge_after=purge_after,
        deletion_export_sha256=payload.export_sha256,
        revoked_api_keys=len(api_keys),
    )


@router.post(
    "/{workspace_id}/restore",
    response_model=WorkspaceRead,
)
def restore_workspace(
    workspace_id: int,
    session: SessionDep,
    user: CurrentUser,
) -> WorkspaceRead:
    workspace, membership = _require_owner_browser(
        session,
        user,
        workspace_id,
        include_deleted=True,
        lock=True,
    )
    if workspace.deletion_requested_at is None or workspace.purge_after is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace is not scheduled for deletion.",
        )
    if workspace.purge_after <= utcnow():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The workspace recovery window has expired.",
        )
    prior_purge_after = workspace.purge_after
    workspace.deletion_requested_at = None
    workspace.purge_after = None
    workspace.deletion_requested_by = None
    workspace.deletion_export_sha256 = None
    session.add(workspace)
    session.add(
        WorkspaceLifecycleEvent(
            workspace_id=workspace_id,
            action=WorkspaceLifecycleAction.DELETION_RESTORED,
            actor_user_id=user.id,
            details={
                "prior_purge_after": f"{prior_purge_after.isoformat()}Z",
                "api_keys_remain_revoked": True,
            },
        )
    )
    session.commit()
    session.refresh(workspace)
    return WorkspaceRead(
        id=workspace_id,
        name=workspace.name,
        slug=workspace.slug,
        role=membership.role,
        created_at=workspace.created_at,
        deletion_requested_at=None,
        purge_after=None,
        deletion_requested_by=None,
        deletion_export_sha256=None,
    )


@router.get(
    "/{workspace_id}/lifecycle-events",
    response_model=list[WorkspaceLifecycleEventRead],
)
def list_workspace_lifecycle_events(
    workspace_id: int,
    session: SessionDep,
    user: CurrentUser,
) -> list[WorkspaceLifecycleEvent]:
    _require_owner_browser(
        session,
        user,
        workspace_id,
        include_deleted=True,
    )
    return list(
        session.exec(
            select(WorkspaceLifecycleEvent)
            .where(WorkspaceLifecycleEvent.workspace_id == workspace_id)
            .order_by(WorkspaceLifecycleEvent.id)
        ).all()
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
