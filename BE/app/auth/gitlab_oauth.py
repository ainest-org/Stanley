from urllib.parse import urlencode

import httpx

from app.core.config import get_settings

settings = get_settings()


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.gitlab_oauth_client_id,
        "redirect_uri": settings.gitlab_oauth_redirect_uri,
        "response_type": "code",
        "scope": settings.gitlab_oauth_scopes,
        "state": state,
    }
    return f"{settings.gitlab_instance_url}/oauth/authorize?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> dict:
    """POST to GitLab's token endpoint. Returns {access_token, refresh_token, expires_in, ...}."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{settings.gitlab_instance_url}/oauth/token",
            data={
                "client_id": settings.gitlab_oauth_client_id,
                "client_secret": settings.gitlab_oauth_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.gitlab_oauth_redirect_uri,
            },
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{settings.gitlab_instance_url}/oauth/token",
            data={
                "client_id": settings.gitlab_oauth_client_id,
                "client_secret": settings.gitlab_oauth_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()


async def fetch_gitlab_user(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{settings.gitlab_instance_url}/api/v4/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()
