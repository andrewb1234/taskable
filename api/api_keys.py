"""Shared API-key issuance helpers.

API keys are high-entropy bearer credentials. The full value is returned only
at issuance; the database stores a deterministic SHA-256 digest for lookup.
Unlike a human password, the generated token has 256 bits of entropy, so a
password KDF is neither necessary nor useful here.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from collections.abc import Iterable

from sqlmodel import Session, select

from api.models.entities import (
    ApiKey,
    ApiKeyProject,
    Project,
    WorkspaceMembership,
)
from api.security import (
    READ_SCOPE,
    VALID_API_KEY_SCOPES,
    WRITE_SCOPE,
)

KEY_PREFIX = "mouvadah_"
KEY_RANDOM_LENGTH = 32  # bytes of entropy -> ~43 URL-safe base64 characters


def hash_api_key(raw_key: str) -> str:
    """Return the stable SHA-256 lookup digest for a random API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a namespaced API key backed by 256 random bits."""
    return f"{KEY_PREFIX}{secrets.token_urlsafe(KEY_RANDOM_LENGTH)}"


def issue_api_key(
    session: Session,
    *,
    user_id: int,
    workspace_id: int,
    name: str,
    scopes: Iterable[str] = (READ_SCOPE, WRITE_SCOPE),
    project_ids: Iterable[int] = (),
    expires_in_days: int | None = None,
) -> tuple[ApiKey, str]:
    """Create an API-key record and return ``(record, full_key_once)``."""
    normalized_scopes = sorted(set(scopes))
    normalized_project_ids = sorted(set(project_ids))
    if (
        not normalized_scopes
        or not set(normalized_scopes).issubset(VALID_API_KEY_SCOPES)
    ):
        raise ValueError("At least one supported API-key scope is required.")
    membership = session.exec(
        select(WorkspaceMembership.id).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    ).first()
    if membership is None:
        raise ValueError("API-key owner must belong to the selected workspace.")
    if normalized_project_ids:
        matching_project_ids = set(
            session.exec(
                select(Project.id).where(
                    Project.id.in_(normalized_project_ids),  # type: ignore[union-attr]
                    Project.workspace_id == workspace_id,
                )
            ).all()
        )
        if matching_project_ids != set(normalized_project_ids):
            raise ValueError(
                "Every API-key project must belong to the selected workspace."
            )

    raw_key = generate_api_key()
    expires_at = None
    if expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    api_key = ApiKey(
        user_id=user_id,
        workspace_id=workspace_id,
        name=name,
        key_prefix=raw_key[:12],
        key_hash=hash_api_key(raw_key),
        scopes=normalized_scopes,
        expires_at=expires_at,
    )
    session.add(api_key)
    session.flush()
    for project_id in normalized_project_ids:
        session.add(
            ApiKeyProject(
                api_key_id=api_key.id,  # type: ignore[arg-type]
                project_id=project_id,
            )
        )
    session.commit()
    session.refresh(api_key)
    return api_key, raw_key
