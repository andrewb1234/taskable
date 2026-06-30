"""Google OAuth routes: login, callback, me, logout.

Flow:
    1. ``GET /auth/login`` → redirect to Google consent screen with a random
       state stored in a short-lived cookie.
    2. Google redirects back to ``GET /auth/callback`` with an authorization
       code. We exchange the code for tokens, fetch the user's Google profile,
       upsert the ``User`` row, set a JWT session cookie, and redirect to the
       frontend.
    3. ``GET /auth/me`` → returns the current user's profile (or 401).
    4. ``POST /auth/logout`` → clears the session cookie.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

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


def _redirect_uri(request: Request) -> str:
    """Derive the OAuth callback URL from the incoming request."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/auth/callback"


def _cookie_kwargs(settings: Settings, max_age: int | None = None) -> dict:
    """Build cookie kwargs. Use Secure in production (HTTPS)."""
    secure = settings.frontend_url.startswith("https://")
    kwargs: dict = {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
    }
    if max_age is not None:
        kwargs["max_age"] = max_age
    return kwargs


@router.get("/login")
async def auth_login(request: Request, settings: SettingsDep) -> RedirectResponse:
    """Redirect the user to Google's OAuth consent screen."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID is not configured",
        )

    state = secrets.token_urlsafe(32)
    redirect_uri = _redirect_uri(request)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "prompt": "select_account",
    }
    auth_url = (
        GOOGLE_AUTH_URL
        + "?"
        + "&".join(f"{k}={v}" for k, v in params.items())
    )

    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        STATE_COOKIE,
        state,
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
    """Handle the OAuth callback: exchange code, upsert user, set JWT cookie."""
    if error:
        return RedirectResponse(
            url=f"{settings.frontend_url}/?auth_error={error}",
            status_code=status.HTTP_302_FOUND,
        )
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code or state parameter",
        )

    # Verify state matches the cookie to prevent CSRF.
    cookie_state = request.cookies.get(STATE_COOKIE)
    if not cookie_state or not secrets.compare_digest(cookie_state, state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    redirect_uri = _redirect_uri(request)

    # Exchange the authorization code for tokens.
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
                detail=f"Token exchange failed: {token_resp.text}",
            )
        tokens = token_resp.json()

        # Fetch user profile from Google.
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Userinfo fetch failed: {userinfo_resp.text}",
            )
        profile = userinfo_resp.json()

    google_id = profile["id"]
    email = profile["email"]
    name = profile.get("name", email)
    avatar_url = profile.get("picture")

    # Upsert the user.
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

    # Issue JWT and set session cookie.
    jwt_token = create_jwt(user.id, user.email, settings.jwt_secret)
    response = RedirectResponse(
        url=settings.frontend_url,
        status_code=status.HTTP_302_FOUND,
    )
    response.set_cookie(
        COOKIE_NAME,
        jwt_token,
        **_cookie_kwargs(settings, max_age=60 * 60 * 24 * 30),  # 30 days
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


@router.post("/logout")
async def auth_logout(
    request: Request,
    settings: SettingsDep,
) -> dict:
    """Clear the session cookie."""
    response = Response(status_code=status.HTTP_200_OK)
    response.delete_cookie(COOKIE_NAME, **_cookie_kwargs(settings))
    return response
