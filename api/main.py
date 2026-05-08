"""FastAPI application entrypoint.

Run locally with::

    cd api && uvicorn main:app --reload

Or from the repo root::

    uvicorn api.main:app --reload

Both forms are supported because the ``Dockerfile.api`` layer copies the
``api`` package into ``/app`` and uses the latter invocation.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.database import init_db
from api.routes import (
    agent,
    comments,
    events,
    knowledge,
    projects,
    proposals,
    sessions,
    subprojects,
    tickets,
)
from api.version import __version__, git_sha


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Taskable Co-Pilot Workspace API",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_v1 = FastAPI(title="Taskable API v1", version=__version__)
    api_v1.include_router(projects.router)
    api_v1.include_router(subprojects.router)
    api_v1.include_router(tickets.router)
    api_v1.include_router(comments.router)
    api_v1.include_router(knowledge.router)
    api_v1.include_router(proposals.router)
    api_v1.include_router(sessions.router)
    api_v1.include_router(events.router)
    api_v1.include_router(agent.router)

    app.mount("/api/v1", api_v1)

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str | None]:
        # Enriched with version + git sha so deployments are debuggable at a
        # glance. Both fields are safe to expose publicly (no secrets).
        return {
            "status": "ok",
            "version": __version__,
            "git_sha": git_sha(),
        }

    return app


app = create_app()
