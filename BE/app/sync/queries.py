"""GraphQL query bodies for the reconciliation pull (PRD Section 11.1).

Field shapes are written against GitLab's documented GraphQL schema but have not been run
against a live self-hosted instance — verify against the target instance's schema during setup
(PRD Section 5.2 step 1) and adjust field names/widget types if that version differs.

Kept single-page (first: 100) for this pass; projects with more open items/MRs than that need
cursor pagination added to `reconciliation.py` before this is production-ready.
"""

PROJECT_RECONCILE_QUERY = """
query($fullPath: ID!) {
  project(fullPath: $fullPath) {
    milestones(first: 100) {
      nodes { id title state startDate dueDate }
    }
    labels(first: 100) {
      nodes { id title color }
    }
    projectMembers(first: 100) {
      nodes {
        user { id username name publicEmail avatarUrl }
        accessLevel { stringValue }
      }
    }
    workItems(first: 100) {
      nodes {
        id
        iid
        title
        state
        createdAt
        updatedAt
        closedAt
        webUrl
        workItemType { name }
        author { id username name publicEmail avatarUrl }
        widgets {
          __typename
          ... on WorkItemWidgetDescription { description }
          ... on WorkItemWidgetAssignees { assignees { nodes { id username name publicEmail avatarUrl } } }
          ... on WorkItemWidgetLabels { labels { nodes { id } } }
          ... on WorkItemWidgetMilestone { milestone { id } }
        }
      }
    }
    mergeRequests(first: 100) {
      nodes {
        id
        iid
        title
        state
        draft
        webUrl
        createdAt
        updatedAt
        mergedAt
        approvalsRequired
        approvalsLeft
        author { id username name publicEmail avatarUrl }
        reviewers { nodes { id username name publicEmail avatarUrl } }
        headPipeline { status }
      }
    }
  }
}
"""

WORK_ITEMS_API_PROBE_QUERY = """
query($fullPath: ID!) {
  project(fullPath: $fullPath) {
    workItems(first: 1) { nodes { id } }
  }
}
"""
