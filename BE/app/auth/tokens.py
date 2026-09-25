"""Access tokens for write-through actions (PRD Section 5.1: "token refresh handled silently in
the background", Section 12: writes run as the acting user, never the service account)."""

from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.gitlab_oauth import refresh_access_token
from app.core.security import decrypt_token, encrypt_token
from app.models.user import User
from app.sync.gitlab_client import GitLabClient

REFRESH_WHEN_UNDER_SECONDS = 120


def token_expiry_iso(token_data: dict) -> str | None:
    expires_in = token_data.get("expires_in")
    if not expires_in:
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()


async def _refresh(db: AsyncSession, user: User) -> str:
    if not user.encrypted_refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your GitLab session expired. Sign out and sign in again.")
    try:
        data = await refresh_access_token(decrypt_token(user.encrypted_refresh_token))
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Your GitLab session expired. Sign out and sign in again."
        ) from exc

    user.encrypted_access_token = encrypt_token(data["access_token"])
    if data.get("refresh_token"):  # GitLab rotates refresh tokens on every use
        user.encrypted_refresh_token = encrypt_token(data["refresh_token"])
    user.token_expires_at = token_expiry_iso(data)
    await db.commit()
    return data["access_token"]


async def get_valid_access_token(db: AsyncSession, user: User) -> tuple[str, dict]:
    """A working GitLab token for this user (refreshed silently if it expired or is about to)
    plus GitLab's info about it. Enough for reads, which only need `read_api`."""
    if not user.encrypted_access_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign in with GitLab again")

    access_token = decrypt_token(user.encrypted_access_token)

    try:
        info = await GitLabClient(access_token=access_token).token_info()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 401:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Could not verify your GitLab token: {exc}") from exc
        access_token = await _refresh(db, user)
        info = await GitLabClient(access_token=access_token).token_info()
    else:
        if (info.get("expires_in_seconds") or 10**9) < REFRESH_WHEN_UNDER_SECONDS:
            access_token = await _refresh(db, user)
            info = await GitLabClient(access_token=access_token).token_info()

    return access_token, info


async def get_write_access_token(db: AsyncSession, user: User) -> str:
    """Like get_valid_access_token, but rejects logins that were granted read-only scopes."""
    access_token, info = await get_valid_access_token(db, user)

    scopes = info.get("scope") or info.get("scopes") or []
    if "api" not in scopes:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Your GitLab login only has these scopes: {', '.join(scopes) or 'none'}. Write actions need "
            "'api'. Enable 'api' on the GitLab OAuth app, set GITLAB_OAUTH_SCOPES=api read_user in "
            "BE/.env, restart the backend, revoke Stanley under GitLab > Preferences > Applications, "
            "then sign out and in again.",
        )
    return access_token
