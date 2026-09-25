import type { QueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface SyncStatus {
  projects: number;
  never_synced: number;
  oldest: string | null;
  newest: string | null;
}

export const fetchSyncStatus = () => apiFetch<SyncStatus>("/api/sync/status");
export const refreshAll = () =>
  apiFetch<{ queued: number; requested_at: string }>("/api/sync/refresh", { method: "POST" });

/** After one of your own actions, Stanley pulls the change back from GitLab within a couple of
 * seconds. Re-read everything once that has had time to finish. */
export function invalidateSoon(queryClient: QueryClient, delayMs = 2500) {
  setTimeout(() => queryClient.invalidateQueries(), delayMs);
}
