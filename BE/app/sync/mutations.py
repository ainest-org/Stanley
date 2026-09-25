"""Write-through mutations (PRD Section 7.5 / 9.3 / 12): every action that changes GitLab data
is a real GitLab API call, executed with the ACTING USER's own OAuth token — never the sync
service account — so the write can never exceed what that person could already do in GitLab
directly (Section 12's permission-mirroring guarantee).

Like `sync/queries.py`, the GraphQL mutation shape here is written against GitLab's documented
schema but not yet verified against a live instance — validate field names during setup.
"""

from app.models.synced_project import SyncedProject
from app.models.work_item import WorkItem
from app.sync.gitlab_client import GitLabClient, GitLabGraphQLError

WORK_ITEM_UPDATE_ASSIGNEE_MUTATION = """
mutation($workItemId: WorkItemID!, $assigneeIds: [UserID!]!) {
  workItemUpdate(input: { id: $workItemId, assigneesWidget: { assigneeIds: $assigneeIds } }) {
    errors
  }
}
"""


async def update_work_item_assignee(
    work_item: WorkItem,
    project: SyncedProject,
    assignee_gitlab_user_id: str,
    acting_user_access_token: str,
) -> None:
    client = GitLabClient(access_token=acting_user_access_token)

    if project.uses_work_items_api:
        data = await client.graphql(
            WORK_ITEM_UPDATE_ASSIGNEE_MUTATION,
            {
                "workItemId": f"gid://gitlab/WorkItem/{work_item.gitlab_global_id}",
                "assigneeIds": [f"gid://gitlab/User/{assignee_gitlab_user_id}"],
            },
        )
        # GraphQL mutations report failures (e.g. missing permission) in `errors` with HTTP 200.
        errors = data["workItemUpdate"]["errors"]
        if errors:
            raise GitLabGraphQLError([{"message": e} for e in errors])
    else:
        await client.rest_put(
            f"/projects/{project.gitlab_project_id}/issues/{work_item.gitlab_iid}",
            {"assignee_ids": [int(assignee_gitlab_user_id)]},
        )


async def create_issue(project: SyncedProject, fields: dict, acting_user_access_token: str) -> dict:
    """Create a work item via the classic Issues REST endpoint (PRD Section 9.3). Every
    work item is an issue underneath, and this endpoint works on every GitLab version."""
    client = GitLabClient(access_token=acting_user_access_token)
    response = await client.rest_post(f"/projects/{project.gitlab_project_id}/issues", fields)
    return response.json()


STANLEY_FOOTER = "_Sent from Stanley_"


async def add_note(project: SyncedProject, kind: str, iid: str, body: str, acting_user_access_token: str) -> None:
    """Post a comment to the real GitLab thread (PRD Section 6.4). kind: issues | merge_requests."""
    client = GitLabClient(access_token=acting_user_access_token)
    await client.rest_post(
        f"/projects/{project.gitlab_project_id}/{kind}/{iid}/notes",
        {"body": f"{body.rstrip()}\n\n{STANLEY_FOOTER}"},
    )


async def set_merge_request_reviewers(
    project: SyncedProject, mr_iid: str, reviewer_gitlab_ids: list[int], acting_user_access_token: str
) -> None:
    """PUT replaces the whole reviewer list, so callers pass existing + new reviewers."""
    client = GitLabClient(access_token=acting_user_access_token)
    await client.rest_put(
        f"/projects/{project.gitlab_project_id}/merge_requests/{mr_iid}", {"reviewer_ids": reviewer_gitlab_ids}
    )
