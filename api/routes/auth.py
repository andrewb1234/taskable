"""Google OAuth routes: login, callback, proxy-callback, me, logout.

Multi-domain OAuth flow (supports PR previews on different hostnames):
    1. ``GET /auth/login`` → encode origin + CSRF token in OAuth state,
       redirect to Google with a stable ``redirect_uri`` (production URL).
    2. Google redirects to ``GET /auth/callback`` on the **production** domain.
       If the origin is production, handle normally (set JWT, redirect home).
       If the origin is a PR preview, forward ``code`` + ``state`` to the
       preview's ``GET /auth/proxy-callback`` endpoint.
    3. ``GET /auth/proxy-callback`` (on the preview domain) → exchange the code
       with Google, upsert user, set JWT cookie on the preview domain, redirect
       to the preview frontend.
    4. ``GET /auth/me`` → returns the current user's profile (or 401).
    5. ``POST /auth/logout`` → clears the session cookie.
"""

from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from api.auth import COOKIE_NAME, create_jwt, get_current_user
from api.config import Settings, get_settings
from api.dependencies import SessionDep, SettingsDep
from api.models.entities import User

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = ["openid", "email", "profile"]

STATE_COOKIE = "oauth_state"
STATE_COOKIE_MAX_AGE = 600  # 10 minutes


def _redirect_uri(request: Request, settings: Settings) -> str:
    """Use the configured stable OAuth redirect URI, or fall back to request host."""
    if settings.oauth_redirect_uri:
        return settings.oauth_redirect_uri
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/auth/callback"


def _cookie_kwargs(settings: Settings, max_age: int | None = None) -> dict:
    """Build cookie kwargs. Use Secure in production (HTTPS)."""
    secure = settings.frontend_url.startswith("https://")
    kwargs: dict = {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
        "path": "/",
    }
    if max_age is not None:
        kwargs["max_age"] = max_age
    return kwargs


def _encode_state(csrf_token: str, origin: str) -> str:
    """Pack CSRF token + origin into a base64 string for the OAuth state param."""
    payload = json.dumps({"csrf": csrf_token, "origin": origin})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_state(state: str) -> dict:
    """Decode the OAuth state parameter back to a dict."""
    return json.loads(base64.urlsafe_b64decode(state.encode()).decode())


def _validate_origin(origin: str, settings: Settings) -> bool:
    """Check that the origin is an allowed domain (prevent open redirect)."""
    if origin == settings.frontend_url:
        return True
    if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
        return True
    for suffix in settings.allowed_origin_suffixes:
        if origin.endswith(suffix):
            return True
    return False


@router.get("/login")
async def auth_login(request: Request, settings: SettingsDep) -> RedirectResponse:
    """Redirect the user to Google's OAuth consent screen.

    Encodes the caller's origin into the OAuth state so the callback knows
    where to send the user after auth completes.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID is not configured",
        )

    csrf_token = secrets.token_urlsafe(32)
    origin = str(request.base_url).rstrip("/")
    state = _encode_state(csrf_token, origin)
    redirect_uri = _redirect_uri(request, settings)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "prompt": "select_account",
    }
    auth_url = GOOGLE_AUTH_URL + "?" + urlencode(params)

    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        STATE_COOKIE,
        csrf_token,
        **_cookie_kwargs(settings, max_age=STATE_COOKIE_MAX_AGE),
    )
    return response


@router.get("/callback")
async def auth_callback(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Handle the OAuth callback on the production domain.

    If the origin in the state is the production domain, handle normally.
    If the origin is a PR preview, forward code+state to the preview's
    proxy-callback endpoint.
    """
    if error:
        return RedirectResponse(
            url=f"{settings.frontend_url}/?auth_error={quote(error)}",
            status_code=status.HTTP_302_FOUND,
        )
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code or state parameter",
        )

    # Decode state to get CSRF token + origin.
    try:
        state_payload = _decode_state(state)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    csrf_token = state_payload.get("csrf", "")
    origin = state_payload.get("origin", "")

    # Verify CSRF token matches the cookie.
    cookie_state = request.cookies.get(STATE_COOKIE)
    if not cookie_state or not secrets.compare_digest(cookie_state, csrf_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    # Validate origin to prevent open redirect.
    if not _validate_origin(origin, settings):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unrecognized origin in OAuth state",
        )

    redirect_uri = _redirect_uri(request, settings)

    # If origin is the production domain, handle locally.
    if origin == str(request.base_url).rstrip("/"):
        return await _complete_auth(
            code, redirect_uri, session, settings, request, origin
        )

    # Origin is a different domain (e.g. PR preview) — forward code + state.
    forward_url = (
        f"{origin}/api/v1/auth/proxy-callback"
        f"?code={quote(code)}&state={quote(state)}"
    )
    response = RedirectResponse(url=forward_url, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(STATE_COOKIE)
    return response


@router.get("/proxy-callback")
async def auth_proxy_callback(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    """Handle forwarded auth code on a PR preview domain.

    Exchanges the code with Google (using the production redirect_uri),
    sets the JWT cookie on this domain, and redirects to the frontend.
    """
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code or state parameter",
        )

    # Decode state to get origin.
    try:
        state_payload = _decode_state(state)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    origin = state_payload.get("origin", "")

    # Validate origin matches the current host (this endpoint is only valid
    # when the forwarded origin matches the domain serving it).
    current_origin = str(request.base_url).rstrip("/")
    if origin != current_origin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Origin mismatch in proxy callback",
        )

    # Use the stable production redirect_uri for the token exchange.
    redirect_uri = _redirect_uri(request, settings)

    return await _complete_auth(
        code, redirect_uri, session, settings, request, origin
    )


async def _complete_auth(
    code: str,
    redirect_uri: str,
    session: Session,
    settings: Settings,
    request: Request,
    origin: str,
) -> RedirectResponse:
    """Exchange code with Google, upsert user, set JWT cookie, redirect to origin."""
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Token exchange failed",
            )
        tokens = token_resp.json()

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Userinfo fetch failed",
            )
        profile = userinfo_resp.json()

    google_id = profile["id"]
    email = profile["email"]
    name = profile.get("name", email)
    avatar_url = profile.get("picture")

    existing = session.exec(
        select(User).where(User.google_id == google_id)
    ).first()
    if existing:
        existing.email = email
        existing.name = name
        existing.avatar_url = avatar_url
        session.add(existing)
        session.commit()
        session.refresh(existing)
        user = existing
    else:
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    jwt_token = create_jwt(user.id, user.email, settings.jwt_secret)
    response = RedirectResponse(url=origin, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        COOKIE_NAME,
        jwt_token,
        **_cookie_kwargs(settings, max_age=60 * 60 * 24 * 30),
    )
    response.delete_cookie(STATE_COOKIE)
    return response


@router.get("/me")
async def auth_me(current_user: User = Depends(get_current_user)) -> dict:
    """Return the current authenticated user's profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "avatar_url": current_user.avatar_url,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def auth_logout(
    request: Request,
    settings: SettingsDep,
) -> Response:
    """Clear the session cookie."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(COOKIE_NAME, **_cookie_kwargs(settings))
    return response
