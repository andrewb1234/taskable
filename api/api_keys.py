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

from sqlmodel import Session

from api.models.entities import ApiKey

KEY_PREFIX = "taskable_"
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
    name: str,
    expires_in_days: int | None = None,
) -> tuple[ApiKey, str]:
    """Create an API-key record and return ``(record, full_key_once)``."""
    raw_key = generate_api_key()
    expires_at = None
    if expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    api_key = ApiKey(
        user_id=user_id,
        name=name,
        key_prefix=raw_key[:12],
        key_hash=hash_api_key(raw_key),
        expires_at=expires_at,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key, raw_key
