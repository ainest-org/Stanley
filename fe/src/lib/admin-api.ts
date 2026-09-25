import { apiFetch } from "@/lib/api";
import type { InToolRole } from "@/lib/api";

export interface GitLabStatus {
  connected: boolean;
  instance_url: string;
  version?: string;
  error?: string;
}

export function fetchGitLabStatus(): Promise<GitLabStatus> {
  return apiFetch<GitLabStatus>("/api/admin/gitlab/status");
}

export interface GitLabProjectOption {
  gitlab_project_id: string;
  name: string;
  full_path: string;
  web_url: string;
  already_synced: boolean;
}

export function searchGitLabProjects(search: string): Promise<GitLabProjectOption[]> {
  const params = new URLSearchParams(search ? { search } : {});
  return apiFetch<GitLabProjectOption[]>(`/api/admin/gitlab/projects?${params.toString()}`);
}

export interface SyncedProject {
  id: string;
  gitlab_project_id: string;
  name: string;
  full_path: string;
  web_url: string;
  is_active: boolean;
  uses_work_items_api: boolean;
  webhook_registered: boolean;
  last_synced_at: string | null;
  last_reconciled_at: string | null;
}

export interface MutationWarnings<T> {
  project: T;
  warnings: string[];
}

export function fetchSyncedProjects(): Promise<SyncedProject[]> {
  return apiFetch<SyncedProject[]>("/api/admin/synced-projects");
}

export function syncProject(gitlabProjectId: string): Promise<MutationWarnings<SyncedProject>> {
  return apiFetch<MutationWarnings<SyncedProject>>("/api/admin/synced-projects", {
    method: "POST",
    body: JSON.stringify({ gitlab_project_id: gitlabProjectId }),
  });
}

export function setSyncedProjectActive(id: string, isActive: boolean): Promise<MutationWarnings<SyncedProject>> {
  return apiFetch<MutationWarnings<SyncedProject>>(`/api/admin/synced-projects/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export interface OrgMember {
  id: string;
  name: string;
  gitlab_username: string;
  email: string;
  avatar_url: string | null;
  in_tool_role: InToolRole;
  has_logged_in: boolean;
}

export function fetchMembers(): Promise<OrgMember[]> {
  return apiFetch<OrgMember[]>("/api/admin/members");
}

export function updateMemberRole(userId: string, role: InToolRole): Promise<OrgMember> {
  return apiFetch<OrgMember>(`/api/admin/members/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ in_tool_role: role }),
  });
}

export interface OrgSettings {
  stale_threshold_days: number;
  stale_recheck_days: number;
  blocked_recheck_days: number;
  review_sla_days: number;
  overloaded_item_threshold: number;
}

export function fetchOrgSettings(): Promise<OrgSettings> {
  return apiFetch<OrgSettings>("/api/admin/settings");
}

export function updateOrgSettings(patch: Partial<OrgSettings>): Promise<OrgSettings> {
  return apiFetch<OrgSettings>("/api/admin/settings", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}
