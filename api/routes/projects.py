"""Project-level endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.events import Event, get_broadcaster
from api.models.entities import Project, Subproject
from api.models.enums import SSEAction
from api.schemas import (
    ProjectCreate,
    ProjectRead,
    SubprojectCreate,
    SubprojectRead,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
def list_projects(session: SessionDep) -> list[Project]:
    return list(session.exec(select(Project).order_by(Project.created_at)).all())


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(payload: ProjectCreate, session: SessionDep) -> Project:
    project = Project(name=payload.name, description=payload.description)
    session.add(project)
    session.commit()
    session.refresh(project)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.PROJECT_CREATED,
            entity="project",
            entity_id=project.id,  # type: ignore[arg-type]
        )
    )
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, session: SessionDep) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.get(
    "/{project_id}/subprojects",
    response_model=list[SubprojectRead],
)
def list_subprojects(project_id: int, session: SessionDep) -> list[Subproject]:
    if session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return list(
        session.exec(
            select(Subproject)
            .where(Subproject.project_id == project_id)
            .order_by(Subproject.id)
        ).all()
    )


@router.post(
    "/{project_id}/subprojects",
    response_model=SubprojectRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_subproject(
    project_id: int,
    payload: SubprojectCreate,
    session: SessionDep,
) -> Subproject:
    if session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    subproject = Subproject(
        project_id=project_id,
        name=payload.name,
        context_brief=payload.context_brief,
        status=payload.status,
    )
    session.add(subproject)
    session.commit()
    session.refresh(subproject)

    await get_broadcaster().publish(
        Event(
            action=SSEAction.SUBPROJECT_CREATED,
            entity="subproject",
            entity_id=subproject.id,  # type: ignore[arg-type]
            parent_id=project_id,
        )
    )
    return subproject
