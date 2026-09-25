"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { timeAgo } from "@/lib/format";
import { fetchSyncStatus, refreshAll } from "@/lib/sync-api";

const POLL_MS = 2000;
const MAX_POLLS = 15;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function RefreshButton() {
  const queryClient = useQueryClient();
  const [syncing, setSyncing] = useState(false);
  const [failed, setFailed] = useState(false);
  const status = useQuery({ queryKey: ["sync", "status"], queryFn: fetchSyncStatus, refetchInterval: 60_000 });

  async function refresh() {
    setSyncing(true);
    setFailed(false);
    try {
      const { requested_at } = await refreshAll();
      const requestedAt = new Date(requested_at).getTime();
      // Wait until every project has synced since the click (or give up after ~30s).
      for (let i = 0; i < MAX_POLLS; i++) {
        await sleep(POLL_MS);
        const current = await fetchSyncStatus();
        if (current.oldest && new Date(current.oldest).getTime() >= requestedAt - 1000) break;
      }
      await queryClient.invalidateQueries();
    } catch {
      setFailed(true);
    } finally {
      setSyncing(false);
    }
  }

  const data = status.data;
  if (data && data.projects === 0) return null;

  let label = "";
  if (failed) label = "Refresh failed. Is the worker running?";
  else if (data?.never_synced) label = "Still syncing for the first time…";
  else if (data?.oldest) label = `Synced ${timeAgo(data.oldest)}`;

  return (
    <div className="space-y-1">
      <Button size="sm" variant="outline" className="w-full" disabled={syncing} onClick={refresh}>
        {syncing ? "Refreshing…" : "Refresh from GitLab"}
      </Button>
      {label && <p className="px-1 text-xs text-muted-foreground">{label}</p>}
    </div>
  );
}
