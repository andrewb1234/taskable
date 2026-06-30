"""JWT utilities and authentication dependencies.

Issues HS256-signed JWTs stored in an ``session`` httpOnly cookie. The
``get_current_user`` dependency is applied to all UI-facing routers so
unauthenticated requests are rejected before reaching business logic.

As a fallback, per-user API keys (``Authorization: Bearer <key>``) are also
accepted so the MCP server can access CRUD routes on behalf of a user.
The full key is hashed (SHA-256) and compared against stored hashes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from api.config import Settings, get_settings
from api.dependencies import SessionDep, SettingsDep
from api.models.entities import ApiKey, User

COOKIE_NAME = "session"
TOKEN_EXPIRY_DAYS = 30

KEY_PREFIX = "taskable_"
KEY_RANDOM_LENGTH = 32  # bytes of entropy -> ~43 base64 chars


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


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of the raw key for storage/lookup."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def verify_api_key(raw_key: str, session: Session) -> User | None:
    """Look up an API key by its hash and return the associated user.

    Returns ``None`` if the key is not found, revoked, or expired.
    Updates ``last_used_at`` on successful verification.
    """
    key_hash = hash_api_key(raw_key)
    api_key = session.exec(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    ).first()
    if api_key is None or api_key.revoked:
        return None
    if api_key.expires_at is not None:
        from api.utils.time import utcnow
        if api_key.expires_at < utcnow():
            return None
    user = session.get(User, api_key.user_id)
    if user is None:
        return None
    from api.utils.time import utcnow as _utcnow
    api_key.last_used_at = _utcnow()
    session.add(api_key)
    session.commit()
    return user


def get_current_user(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    """Dependency that extracts and validates the user from either:
    1. A session cookie (JWT), or
    2. A per-user API key (Authorization: Bearer <key>).
    """
    # Try session cookie first.
    token = request.cookies.get(COOKIE_NAME)
    if token:
        payload = decode_jwt(token, settings.jwt_secret)
        if payload is not None:
            user_id = int(payload["sub"])
            user = session.get(User, user_id)
            if user is not None:
                request.state.auth_method = "cookie"
                return user

    # Fallback: per-user API key bearer token.
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        bearer_token = authorization[len("Bearer "):]
        user = verify_api_key(bearer_token, session)
        if user is not None:
            request.state.auth_method = "api_key"
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


CurrentUser = Annotated[User, Depends(get_current_user)]
