import { apiFetch } from "@/lib/api";

export type MrStatus = "draft" | "open" | "approved" | "pipeline_failing" | "merged" | null;

export interface WorkCard {
  kind: "work_item" | "merge_request";
  id: string;
  title: string;
  project_name: string;
  web_url: string;
  mr_status: MrStatus;
  last_activity_at: string;
  is_flagged: boolean;
  blocked_reason: string | null;
}

export interface MyWork {
  doing_now: WorkCard[];
  up_next: WorkCard[];
  waiting_on_others: WorkCard[];
  review_requests: WorkCard[];
}

export function fetchMyWork(): Promise<MyWork> {
  return apiFetch<MyWork>("/api/my-work");
}

export function markWorkItemBlocked(workItemId: string, reason: string): Promise<unknown> {
  return apiFetch(`/api/work-items/${workItemId}/blocked`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function unblockWorkItem(workItemId: string): Promise<unknown> {
  return apiFetch(`/api/work-items/${workItemId}/unblock`, { method: "POST" });
}

export interface SwimlaneItem {
  id: string;
  title: string;
  project_name: string;
  web_url: string;
  is_blocked: boolean;
  is_stale: boolean;
}

export interface Swimlane {
  user_id: string;
  name: string;
  avatar_url: string | null;
  active_count: number;
  blocked_count: number;
  stale_count: number;
  items: SwimlaneItem[];
}

export interface AttentionItem {
  id: string;
  title: string;
  project_name?: string;
  web_url: string;
  days_inactive?: number;
  days_pending?: number;
  reviewer_name?: string;
}

export interface TeamBoard {
  swimlanes: Swimlane[];
  attention: {
    stalled_mrs: AttentionItem[];
    unassigned_items: AttentionItem[];
    reviews_pending_sla: AttentionItem[];
    idle_engineers: { user_id: string; name: string }[];
    overloaded_engineers: { user_id: string; name: string; active_count: number }[];
  };
}

export function fetchTeamBoard(): Promise<TeamBoard> {
  return apiFetch<TeamBoard>("/api/team-board");
}

export function reassignWorkItem(workItemId: string, assigneeUserId: string): Promise<unknown> {
  return apiFetch(`/api/work-items/${workItemId}/assignee`, {
    method: "PATCH",
    body: JSON.stringify({ assignee_user_id: assigneeUserId }),
  });
}

export interface RadarSummary {
  in_progress: number;
  blocked: number;
  in_review: number;
  shipped_this_week: number;
}

export interface DeliveryTrendPoint {
  week_start: string;
  merged_count: number;
  closed_count: number;
}

export interface ProjectHealth {
  project_id: string;
  name: string;
  status: "green" | "yellow" | "red" | "no_active_milestone";
  milestone_title: string | null;
  percent_done: number | null;
}

export interface Blocker {
  work_item_id: string;
  title: string;
  project_name: string;
  web_url: string;
  blocked_days: number;
  reason: string;
  assignee_name: string | null;
}

export interface RadarPerson {
  user_id: string;
  name: string;
  active_count: number;
  blocked_count: number;
}

export interface Radar {
  as_of: string;
  summary: RadarSummary;
  delivery_trend: DeliveryTrendPoint[];
  project_health: ProjectHealth[];
  blockers: Blocker[];
  people: RadarPerson[];
}

export function fetchRadar(): Promise<Radar> {
  return apiFetch<Radar>("/api/radar");
}
