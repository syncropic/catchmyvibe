"""Authentication routes for streaming services."""

import base64
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_session
from models import StreamingServiceToken

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()

# In-memory state storage (use Redis in production)
oauth_states: dict[str, dict] = {}


# =============================================================================
# SPOTIFY OAUTH
# =============================================================================

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_USER_URL = "https://api.spotify.com/v1/me"

# Scopes needed for liked songs and library access
SPOTIFY_SCOPES = [
    "user-library-read",      # Read saved tracks
    "user-read-private",      # Read user profile
    "user-read-email",        # Read user email
    "playlist-read-private",  # Read private playlists
    "playlist-read-collaborative",  # Read collaborative playlists
]


@router.get("/spotify/login")
async def spotify_login(
    redirect_uri: Optional[str] = Query(None, description="Where to redirect after auth"),
) -> RedirectResponse:
    """Initiate Spotify OAuth login flow."""
    if not settings.spotify_client_id:
        raise HTTPException(status_code=500, detail="Spotify client ID not configured")

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    oauth_states[state] = {
        "created_at": datetime.now(timezone.utc),
        "redirect_uri": redirect_uri or "http://127.0.0.1:3000/import",
    }

    # Build authorization URL
    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "state": state,
        "scope": " ".join(SPOTIFY_SCOPES),
        "show_dialog": "true",  # Always show auth dialog
    }

    auth_url = f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/spotify/callback")
async def spotify_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle Spotify OAuth callback."""
    # Check for errors
    if error:
        raise HTTPException(status_code=400, detail=f"Spotify auth error: {error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")

    # Validate state
    state_data = oauth_states.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    # Check state expiry (5 minutes)
    if datetime.now(timezone.utc) - state_data["created_at"] > timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="State expired")

    redirect_uri = state_data["redirect_uri"]

    # Exchange code for tokens
    try:
        tokens = await _exchange_spotify_code(code)
    except Exception as e:
        return RedirectResponse(url=f"{redirect_uri}?error=token_exchange_failed&message={str(e)}")

    # Get user profile
    try:
        user_profile = await _get_spotify_user_profile(tokens["access_token"])
    except Exception as e:
        return RedirectResponse(url=f"{redirect_uri}?error=profile_fetch_failed&message={str(e)}")

    # Store or update token
    stmt = select(StreamingServiceToken).where(
        StreamingServiceToken.service == "spotify",
        StreamingServiceToken.service_user_id == user_profile["id"],
    )
    result = await session.execute(stmt)
    existing_token = result.scalar_one_or_none()

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))

    if existing_token:
        existing_token.access_token = tokens["access_token"]
        existing_token.refresh_token = tokens.get("refresh_token", existing_token.refresh_token)
        existing_token.expires_at = expires_at
        existing_token.is_active = True
        existing_token.service_user_email = user_profile.get("email")
        existing_token.service_user_name = user_profile.get("display_name")
    else:
        new_token = StreamingServiceToken(
            service="spotify",
            service_user_id=user_profile["id"],
            service_user_email=user_profile.get("email"),
            service_user_name=user_profile.get("display_name"),
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_type=tokens.get("token_type", "Bearer"),
            expires_at=expires_at,
            scopes=" ".join(SPOTIFY_SCOPES),
            is_active=True,
        )
        session.add(new_token)

    await session.commit()

    # Redirect back to frontend with success
    return RedirectResponse(url=f"{redirect_uri}?spotify=connected&user={user_profile.get('display_name', 'User')}")


@router.get("/spotify/status")
async def spotify_status(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get current Spotify connection status."""
    stmt = select(StreamingServiceToken).where(
        StreamingServiceToken.service == "spotify",
        StreamingServiceToken.is_active == True,  # noqa: E712
    ).order_by(StreamingServiceToken.updated_at.desc())

    result = await session.execute(stmt)
    token = result.scalar_one_or_none()

    if not token:
        return {
            "connected": False,
            "user": None,
            "last_sync": None,
            "tracks_synced": 0,
        }

    return {
        "connected": True,
        "user": {
            "id": token.service_user_id,
            "email": token.service_user_email,
            "name": token.service_user_name,
        },
        "last_sync": token.last_sync_at.isoformat() if token.last_sync_at else None,
        "tracks_synced": token.tracks_synced,
        "token_expires": token.expires_at.isoformat() if token.expires_at else None,
        "is_expired": token.is_expired(),
    }


@router.post("/spotify/disconnect")
async def spotify_disconnect(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Disconnect Spotify account."""
    stmt = select(StreamingServiceToken).where(
        StreamingServiceToken.service == "spotify",
        StreamingServiceToken.is_active == True,  # noqa: E712
    )
    result = await session.execute(stmt)
    tokens = result.scalars().all()

    for token in tokens:
        token.is_active = False

    await session.commit()

    return {"message": "Spotify disconnected", "tokens_deactivated": len(tokens)}


@router.post("/spotify/refresh")
async def spotify_refresh_token(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Manually refresh Spotify access token."""
    stmt = select(StreamingServiceToken).where(
        StreamingServiceToken.service == "spotify",
        StreamingServiceToken.is_active == True,  # noqa: E712
    ).order_by(StreamingServiceToken.updated_at.desc())

    result = await session.execute(stmt)
    token = result.scalar_one_or_none()

    if not token:
        raise HTTPException(status_code=404, detail="No active Spotify connection")

    if not token.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")

    try:
        new_tokens = await _refresh_spotify_token(token.refresh_token)

        token.access_token = new_tokens["access_token"]
        if "refresh_token" in new_tokens:
            token.refresh_token = new_tokens["refresh_token"]
        token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_tokens.get("expires_in", 3600))

        await session.commit()

        return {
            "message": "Token refreshed",
            "expires_at": token.expires_at.isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh token: {str(e)}")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def _exchange_spotify_code(code: str) -> dict:
    """Exchange authorization code for access token."""
    auth_str = f"{settings.spotify_client_id}:{settings.spotify_client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPOTIFY_TOKEN_URL,
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
            },
        )

        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")

        return response.json()


async def _refresh_spotify_token(refresh_token: str) -> dict:
    """Refresh an expired access token."""
    auth_str = f"{settings.spotify_client_id}:{settings.spotify_client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPOTIFY_TOKEN_URL,
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")

        return response.json()


async def _get_spotify_user_profile(access_token: str) -> dict:
    """Get user profile from Spotify."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            SPOTIFY_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get user profile: {response.text}")

        return response.json()


async def get_active_spotify_token(session: AsyncSession) -> Optional[StreamingServiceToken]:
    """Get the active Spotify token, refreshing if needed."""
    stmt = select(StreamingServiceToken).where(
        StreamingServiceToken.service == "spotify",
        StreamingServiceToken.is_active == True,  # noqa: E712
    ).order_by(StreamingServiceToken.updated_at.desc())

    result = await session.execute(stmt)
    token = result.scalar_one_or_none()

    if not token:
        return None

    # Refresh if expired or about to expire (within 5 minutes)
    if token.expires_at:
        buffer_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        if token.expires_at <= buffer_time and token.refresh_token:
            try:
                new_tokens = await _refresh_spotify_token(token.refresh_token)
                token.access_token = new_tokens["access_token"]
                if "refresh_token" in new_tokens:
                    token.refresh_token = new_tokens["refresh_token"]
                token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_tokens.get("expires_in", 3600))
                await session.commit()
            except Exception:
                # If refresh fails, return the possibly expired token
                pass

    return token
