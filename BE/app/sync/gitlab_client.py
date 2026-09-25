import httpx

from app.core.config import get_settings

settings = get_settings()

GRAPHQL_PATH = "/api/graphql"


class GitLabRateLimited(Exception):
    """Raised on a 429 from GitLab. Carries the server's Retry-After hint (seconds) so the
    caller can back off per-project rather than hammering every project on the same tick
    (PRD Section 13.1)."""

    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"GitLab rate-limited us; retry after {retry_after_seconds}s")


class GitLabGraphQLError(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(str(errors))


class GitLabClient:
    """Thin wrapper over GitLab's GraphQL (primary) and REST (fallback) APIs (PRD Section 15).

    `access_token` is either a per-user OAuth token (calls scoped to that user's own GitLab
    permissions, Section 12) or the org-wide sync service account token (Section 5.2 step 1 /
    NFR Section 14: service accounts only for org-wide sync jobs).
    """

    def __init__(self, access_token: str, instance_url: str | None = None):
        self._access_token = access_token
        self._base_url = (instance_url or settings.gitlab_instance_url).rstrip("/")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    @staticmethod
    def _raise_for_rate_limit(response: httpx.Response) -> None:
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise GitLabRateLimited(retry_after)

    async def graphql(self, query: str, variables: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url}{GRAPHQL_PATH}",
                headers=self._headers(),
                json={"query": query, "variables": variables or {}},
            )
        self._raise_for_rate_limit(response)
        response.raise_for_status()
        body = response.json()
        if "errors" in body and body["errors"]:
            raise GitLabGraphQLError(body["errors"])
        return body["data"]

    async def rest_get(self, path: str, params: dict | None = None) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._base_url}/api/v4{path}",
                headers=self._headers(),
                params=params or {},
            )
        self._raise_for_rate_limit(response)
        response.raise_for_status()
        return response

    async def rest_post(self, path: str, json: dict | None = None) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url}/api/v4{path}",
                headers=self._headers(),
                json=json or {},
            )
        self._raise_for_rate_limit(response)
        response.raise_for_status()
        return response

    async def rest_put(self, path: str, json: dict | None = None) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.put(
                f"{self._base_url}/api/v4{path}",
                headers=self._headers(),
                json=json or {},
            )
        self._raise_for_rate_limit(response)
        response.raise_for_status()
        return response

    async def rest_delete(self, path: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.delete(f"{self._base_url}/api/v4{path}", headers=self._headers())
        self._raise_for_rate_limit(response)
        if response.status_code != 404:
            response.raise_for_status()

    async def supports_work_items_api(self, project_full_path: str) -> bool:
        """Detected at setup (PRD Section 5.2 step 1 / 13.1 last row): older self-hosted GitLab
        instances lack the Work Items API and must fall back to the classic Issues API."""
        from app.sync.queries import WORK_ITEMS_API_PROBE_QUERY

        try:
            await self.graphql(WORK_ITEMS_API_PROBE_QUERY, {"fullPath": project_full_path})
            return True
        except GitLabGraphQLError:
            return False
