"""Write-through for linking work items to merge requests and milestones, always executed with
the acting user's own GitLab token (PRD Section 12)."""

from app.models.synced_project import SyncedProject
from app.sync.gitlab_client import GitLabClient
from app.sync.mr_links import add_reference, remove_reference


async def update_merge_request_references(
    project: SyncedProject,
    mr_iid: str,
    issue_iid: str,
    acting_user_access_token: str,
    *,
    link: bool,
    closes: bool = False,
) -> tuple[str, str]:
    """Link / unlink a work item by editing the merge request description in GitLab, the same
    reference GitLab itself uses. Returns the MR's (title, resulting description)."""
    client = GitLabClient(access_token=acting_user_access_token)
    path = f"/projects/{project.gitlab_project_id}/merge_requests/{mr_iid}"
    mr = (await client.rest_get(path)).json()
    old = mr.get("description") or ""
    new = add_reference(old, issue_iid, closes) if link else remove_reference(old, issue_iid)
    if new != old:
        await client.rest_put(path, {"description": new})
    return mr.get("title") or "", new


async def set_issue_milestone(
    project: SyncedProject, issue_iid: str, milestone_gitlab_id: int | None, acting_user_access_token: str
) -> None:
    """milestone_id 0 clears the milestone in GitLab's REST API."""
    client = GitLabClient(access_token=acting_user_access_token)
    await client.rest_put(
        f"/projects/{project.gitlab_project_id}/issues/{issue_iid}", {"milestone_id": milestone_gitlab_id or 0}
    )
