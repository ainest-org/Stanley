import { ApiError, apiFetch } from "@/lib/api";

export interface ProjectOption {
  id: string;
  name: string;
}

export interface PersonOption {
  id: string;
  name: string;
}

export interface CreateOptions {
  members: PersonOption[];
  milestones: { id: string; title: string }[];
  labels: { id: string; name: string; color: string | null }[];
}

export const fetchProjects = () => apiFetch<ProjectOption[]>("/api/projects");
export const fetchAllMembers = () => apiFetch<PersonOption[]>("/api/members");
export const fetchCreateOptions = (projectId: string) =>
  apiFetch<CreateOptions>(`/api/projects/${projectId}/create-options`);

export interface CreateWorkItemInput {
  project_id: string;
  title: string;
  idempotency_key: string;
  item_type: "issue" | "task" | "incident";
  description?: string;
  assignee_user_id?: string;
  milestone_id?: string;
  label_ids: string[];
  due_date?: string;
}

export const createWorkItem = (input: CreateWorkItemInput) =>
  apiFetch<{ id: string; web_url: string; duplicate: boolean }>("/api/work-items", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const commentOn = (kind: "work_item" | "merge_request", id: string, body: string) =>
  apiFetch(`/api/${kind === "work_item" ? "work-items" : "merge-requests"}/${id}/comment`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });

export const requestReview = (mergeRequestId: string, reviewerUserId: string) =>
  apiFetch(`/api/merge-requests/${mergeRequestId}/reviewers`, {
    method: "POST",
    body: JSON.stringify({ reviewer_user_id: reviewerUserId }),
  });

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    try {
      const detail = JSON.parse(error.message).detail;
      return typeof detail === "string" ? detail : JSON.stringify(detail);
    } catch {
      return error.message;
    }
  }
  return "Something went wrong";
}

export interface LinkableMergeRequest {
  id: string;
  title: string;
  iid: string;
  author: string | null;
  mine: boolean;
}

export const fetchLinkableMergeRequests = (workItemId: string) =>
  apiFetch<LinkableMergeRequest[]>(`/api/work-items/${workItemId}/linkable-merge-requests`);

export const linkMergeRequest = (workItemId: string, mergeRequestId: string, closes: boolean) =>
  apiFetch<{ ok: boolean; linked_to_this_item: boolean; note: string | null }>(
    `/api/work-items/${workItemId}/merge-requests`,
    { method: "POST", body: JSON.stringify({ merge_request_id: mergeRequestId, closes }) },
  );

export const unlinkMergeRequest = (workItemId: string, mergeRequestId: string) =>
  apiFetch<{ ok: boolean; still_linked: boolean; note: string | null }>(
    `/api/work-items/${workItemId}/merge-requests/${mergeRequestId}`,
    { method: "DELETE" },
  );

export const setWorkItemMilestone = (workItemId: string, milestoneId: string | null) =>
  apiFetch(`/api/work-items/${workItemId}/milestone`, {
    method: "PATCH",
    body: JSON.stringify({ milestone_id: milestoneId }),
  });
