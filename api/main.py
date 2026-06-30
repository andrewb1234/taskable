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
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from api.auth import get_current_user
from api.config import get_settings
from api.database import init_db
from api.routes import (
    agent,
    auth,
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

    # Build CORS origins from config + frontend_url.
    cors_origins = list(settings.cors_origins)
    if settings.frontend_url not in cors_origins:
        cors_origins.append(settings.frontend_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- API v1 ---
    api_v1 = FastAPI(title="Taskable API v1", version=__version__)

    # Public routes (no auth).
    api_v1.include_router(auth.router)

    # UI-facing routes (require authenticated user).
    ui_auth = [Depends(get_current_user)]
    api_v1.include_router(projects.router, dependencies=ui_auth)
    api_v1.include_router(subprojects.router, dependencies=ui_auth)
    api_v1.include_router(tickets.router, dependencies=ui_auth)
    api_v1.include_router(comments.router, dependencies=ui_auth)
    api_v1.include_router(knowledge.router, dependencies=ui_auth)
    api_v1.include_router(proposals.router, dependencies=ui_auth)
    api_v1.include_router(sessions.router, dependencies=ui_auth)
    api_v1.include_router(events.router, dependencies=ui_auth)

    # Agent routes (bearer token auth, not user session).
    api_v1.include_router(agent.router)

    app.mount("/api/v1", api_v1)
    app.api_v1 = api_v1  # exposed for test dependency overrides

    # --- Health check ---
    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str | None]:
        return {
            "status": "ok",
            "version": __version__,
            "git_sha": git_sha(),
        }

    # --- Serve built frontend (production) ---
    dist_dir = Path("web/dist")
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        async def spa_catch_all(full_path: str):
            """SPA fallback: serve index.html for any non-API path."""
            return FileResponse(str(dist_dir / "index.html"))

    return app


app = create_app()
