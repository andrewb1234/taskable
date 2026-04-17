"""FastAPI dependencies: session + agent bearer auth."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from api.config import Settings, get_settings
from api.database import get_session


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_agent_key(
    authorization: Annotated[str | None, Header()] = None,
    settings: SettingsDep = None,  # type: ignore[assignment]
) -> None:
    """Guard agent-only endpoints via a static bearer token.

    The UI running on localhost does not need to pass this header; it is only
    enforced on routes that explicitly depend on ``require_agent_key``.
    """
    if settings is None:  # defensive; FastAPI always injects
        settings = get_settings()
    expected = f"Bearer {settings.agent_api_key}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing agent API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
