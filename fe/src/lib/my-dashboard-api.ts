import { apiFetch } from "@/lib/api";

export interface MyStats {
  merged_this_week: number;
  merged_last_week: number;
  closed_this_week: number;
  trend: { week_start: string; merged: number; closed: number }[];
  median_cycle_days: number | null;
  pipeline_pass_rate: number | null;
  open_items: number;
  oldest_open_item_days: number | null;
  reviews_waiting: number;
  oldest_review_waiting_days: number | null;
  reviews_approved_recent: number;
}

export interface MyAttention {
  reviews_waiting: { id: string; title: string; web_url: string; days_waiting: number; overdue: boolean }[];
  failing_pipelines: { id: string; title: string; web_url: string; pipeline_url: string }[];
  stale_items: { id: string; title: string; web_url: string; days_inactive: number }[];
}

export interface ActivityEvent {
  kind: "merged" | "opened" | "closed";
  title: string;
  web_url: string;
  at: string;
}

export interface MyOverview {
  stats: MyStats;
  attention: MyAttention;
  activity: ActivityEvent[];
}

export const fetchMyOverview = () => apiFetch<MyOverview>("/api/my-work/overview");

export const updateItemPreferences = (
  workItemId: string,
  patch: { watching?: boolean; snoozed_until?: string | null },
) =>
  apiFetch(`/api/work-items/${workItemId}/preferences`, {
    method: "PUT",
    body: JSON.stringify(patch),
  });

export interface Todo {
  id: string;
  action: string;
  target_type: string | null;
  title: string;
  body: string;
  author: string | null;
  project: string | null;
  url: string | null;
  created_at: string;
  work_item_id: string | null;
  merge_request_id: string | null;
}

export const fetchTodos = () => apiFetch<{ todos: Todo[]; live_error: string | null }>("/api/todos");
export const markTodoDone = (id: string) => apiFetch(`/api/todos/${id}/done`, { method: "POST" });
export const markAllTodosDone = () => apiFetch("/api/todos/done-all", { method: "POST" });

export interface CheckInState {
  date: string;
  submitted: boolean;
  skipped: boolean;
  saved: { did: string | null; doing: string | null; blockers: string | null } | null;
  prefill: { did: string; doing: string; blockers: string };
}

export const fetchCheckIn = () => apiFetch<CheckInState>("/api/check-ins/today");
export const saveCheckIn = (body: { did: string; doing: string; blockers: string }) =>
  apiFetch("/api/check-ins/today", { method: "PUT", body: JSON.stringify(body) });
export const skipCheckIn = () => apiFetch("/api/check-ins/today/skip", { method: "POST" });
