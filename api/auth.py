"""JWT utilities and authentication dependencies.

Issues HS256-signed JWTs stored in an ``session`` httpOnly cookie. The
``get_current_user`` dependency is applied to all UI-facing routers so
unauthenticated requests are rejected before reaching business logic.

As a fallback, agent bearer tokens (``Authorization: Bearer <AGENT_API_KEY>``)
are also accepted so the MCP server can access CRUD routes without a session
cookie. When bearer auth is used, a synthetic system user is returned.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from api.config import Settings, get_settings
from api.dependencies import SessionDep, SettingsDep
from api.models.entities import User

COOKIE_NAME = "session"
TOKEN_EXPIRY_DAYS = 30

# Synthetic user IDs for agent-authenticated requests (negative to avoid collision).
_AGENT_USER_ID = -1


def create_jwt(user_id: int, email: str, secret: str) -> str:
    """Sign a JWT containing the user ID and email."""
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_jwt(token: str, secret: str) -> dict | None:
    """Verify and decode a JWT. Returns ``None`` on failure."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _agent_user() -> User:
    """Return a synthetic system user for agent-bearer-authenticated requests."""
    return User(
        id=_AGENT_USER_ID,
        google_id="agent",
        email="agent@taskable.local",
        name="Agent",
        avatar_url=None,
    )


def get_current_user(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    """Dependency that extracts and validates the user from either:
    1. A session cookie (JWT), or
    2. An agent bearer token (Authorization: Bearer <AGENT_API_KEY>).
    """
    # Try session cookie first.
    token = request.cookies.get(COOKIE_NAME)
    if token:
        payload = decode_jwt(token, settings.jwt_secret)
        if payload is not None:
            user_id = int(payload["sub"])
            user = session.get(User, user_id)
            if user is not None:
                return user

    # Fallback: agent bearer token.
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        bearer_token = authorization[len("Bearer "):]
        if bearer_token == settings.agent_api_key:
            return _agent_user()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


CurrentUser = Annotated[User, Depends(get_current_user)]
