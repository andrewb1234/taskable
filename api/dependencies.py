"""FastAPI dependency aliases shared by route modules."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from api.config import Settings, get_settings
from api.database import get_session


SessionDep = Annotated[Session, Depends(get_session)]
FunctionSessionDep = Annotated[
    Session,
    Depends(get_session, scope="function"),
]
SettingsDep = Annotated[Settings, Depends(get_settings)]
