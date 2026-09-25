import uuid

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_session_token
from app.db.session import get_db
from app.models.user import InToolRole, User


async def get_current_user(
    session_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = decode_session_token(session_token)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")

    user = await db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or deactivated")

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """In-tool Admin role gate (PRD Section 3/12) for the setup/settings screens. This only
    restricts which screens are reachable — it never grants extra GitLab access beyond what
    the admin's own OAuth-scoped token already allows on any given GitLab call."""
    if current_user.in_tool_role != InToolRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return current_user


async def require_manager(current_user: User = Depends(get_current_user)) -> User:
    """Managers and admins only (in-tool roles, PRD Section 3): the standup digest reads other
    people's check-ins."""
    if current_user.in_tool_role not in (InToolRole.MANAGER, InToolRole.ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager role required")
    return current_user
