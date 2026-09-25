"""Write-through mutations (PRD Section 7.5 / 9.3 / 12): every action that changes GitLab data
is a real GitLab API call, executed with the ACTING USER's own OAuth token — never the sync
service account — so the write can never exceed what that person could already do in GitLab
directly (Section 12's permission-mirroring guarantee).

Like `sync/queries.py`, the GraphQL mutation shape here is written against GitLab's documented
schema but not yet verified against a live instance — validate field names during setup.
"""

from app.models.synced_project import SyncedProject
from app.models.work_item import WorkItem
from app.sync.gitlab_client import GitLabClient

WORK_ITEM_UPDATE_ASSIGNEE_MUTATION = """
mutation($workItemId: WorkItemID!, $assigneeIds: [UserID!]!) {
  workItemUpdateWidgets(input: { id: $workItemId, assigneesWidget: { assigneeIds: $assigneeIds } }) {
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
        await client.graphql(
            WORK_ITEM_UPDATE_ASSIGNEE_MUTATION,
            {
                "workItemId": f"gid://gitlab/WorkItem/{work_item.gitlab_global_id}",
                "assigneeIds": [f"gid://gitlab/User/{assignee_gitlab_user_id}"],
            },
        )
    else:
        await client.rest_put(
            f"/projects/{project.gitlab_project_id}/issues/{work_item.gitlab_iid}",
            {"assignee_ids": [int(assignee_gitlab_user_id)]},
        )
