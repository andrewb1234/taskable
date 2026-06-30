"""API key management routes.

Users can create, list, and revoke per-user API keys for agent/MCP access.
The full key is returned only once on creation — thereafter only the prefix
is shown for identification.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import select

from api.auth import KEY_PREFIX, KEY_RANDOM_LENGTH, CurrentUser, hash_api_key
from api.dependencies import SessionDep
from api.models.entities import ApiKey

router = APIRouter(prefix="/apikeys", tags=["apikeys"])


class CreateApiKeyRequest(BaseModel):
    name: str = "Default"
    expires_in_days: Optional[int] = None


class ApiKeyOut(BaseModel):
    id: int
    name: str
    key_prefix: str
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    created_at: datetime
    revoked: bool


class ApiKeyCreated(ApiKeyOut):
    key: str  # full key, shown once


def _generate_key() -> str:
    """Generate a random API key: taskable_<random43>."""
    random_part = secrets.token_urlsafe(KEY_RANDOM_LENGTH)
    return f"{KEY_PREFIX}{random_part}"


def _to_out(api_key: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        revoked=api_key.revoked,
    )


@router.get("")
async def list_api_keys(
    session: SessionDep,
    user: CurrentUser,
) -> list[ApiKeyOut]:
    """List all API keys for the current user (non-revoked first)."""
    keys = session.exec(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.revoked, ApiKey.created_at.desc())
    ).all()
    return [_to_out(k) for k in keys]


@router.post("")
async def create_api_key(
    payload: CreateApiKeyRequest,
    session: SessionDep,
    user: CurrentUser,
) -> ApiKeyCreated:
    """Create a new API key. The full key is returned only once."""
    raw_key = _generate_key()
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:12]

    expires_at = None
    if payload.expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=payload.expires_in_days
        )

    api_key = ApiKey(
        user_id=user.id,
        name=payload.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        expires_at=expires_at,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        revoked=api_key.revoked,
        key=raw_key,
    )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: int,
    session: SessionDep,
    user: CurrentUser,
) -> dict:
    """Revoke an API key by ID. Only the key owner can revoke."""
    api_key = session.get(ApiKey, key_id)
    if api_key is None or api_key.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    api_key.revoked = True
    session.add(api_key)
    session.commit()
    return {"status": "revoked"}
