import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.tokens import token_expiry_iso
from app.auth.gitlab_oauth import build_authorize_url, exchange_code_for_token, fetch_gitlab_user
from app.core.config import get_settings
from app.core.org import get_or_create_default_organization
from app.core.security import create_session_token, encrypt_token
from app.db.session import get_db
from app.models.user import InToolRole, User

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()

OAUTH_STATE_COOKIE = "oauth_state"
SESSION_COOKIE = "session_token"


@router.get("/login")
async def login() -> RedirectResponse:
    """Kicks off GitLab OAuth2 (PRD Section 5.1): redirect the browser to GitLab's
    authorize screen. State is round-tripped via an httponly cookie to prevent CSRF."""
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(build_authorize_url(state))
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        httponly=True,
        samesite="lax",
        max_age=600,
        secure=settings.app_env != "development",
    )
    return response


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    oauth_state: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if not oauth_state or oauth_state != state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid OAuth state")

    token_data = await exchange_code_for_token(code)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")

    gitlab_user = await fetch_gitlab_user(access_token)

    organization = await get_or_create_default_organization(db)

    result = await db.execute(select(User).where(User.gitlab_user_id == str(gitlab_user["id"])))
    user = result.scalar_one_or_none()

    encrypted_access = encrypt_token(access_token)
    encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None
    expires_at = token_expiry_iso(token_data)

    if user is None:
        # Nobody has ever signed in for this org yet (first-run) — that person needs Admin to
        # reach GitLab connection/project-sync setup (PRD Section 5.2), so bootstrap them as one.
        existing_users = await db.execute(select(User.id).where(User.organization_id == organization.id).limit(1))
        is_first_user = existing_users.scalar_one_or_none() is None

        user = User(
            organization_id=organization.id,
            gitlab_user_id=str(gitlab_user["id"]),
            gitlab_username=gitlab_user["username"],
            email=gitlab_user.get("email") or "",
            name=gitlab_user.get("name") or gitlab_user["username"],
            avatar_url=gitlab_user.get("avatar_url"),
            encrypted_access_token=encrypted_access,
            encrypted_refresh_token=encrypted_refresh,
            token_expires_at=expires_at,
            in_tool_role=InToolRole.ADMIN if is_first_user else InToolRole.ENGINEER,
        )
        db.add(user)
    else:
        user.gitlab_username = gitlab_user["username"]
        user.email = gitlab_user.get("email") or user.email
        user.name = gitlab_user.get("name") or user.name
        user.avatar_url = gitlab_user.get("avatar_url")
        user.encrypted_access_token = encrypted_access
        user.encrypted_refresh_token = encrypted_refresh
        user.token_expires_at = expires_at

    await db.commit()
    await db.refresh(user)

    session_token = create_session_token(str(user.id))

    response = RedirectResponse(f"{settings.frontend_base_url}/auth/complete")
    response.delete_cookie(OAUTH_STATE_COOKIE)
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        secure=settings.app_env != "development",
    )
    return response


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
        "gitlab_username": current_user.gitlab_username,
        "avatar_url": current_user.avatar_url,
        "in_tool_role": current_user.in_tool_role.value,
    }


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}
