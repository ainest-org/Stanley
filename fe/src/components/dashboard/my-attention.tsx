"use client";

import { AlertTriangle } from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";
import { type MyAttention } from "@/lib/my-dashboard-api";

export function MyAttentionStrip({ attention }: { attention: MyAttention }) {
  const { reviews_waiting, failing_pipelines, stale_items } = attention;
  const total = reviews_waiting.length + failing_pipelines.length + stale_items.length;
  if (total === 0) return null;

  return (
    <div className="rounded-xl border border-amber-300/60 bg-amber-50 p-3 dark:border-amber-500/30 dark:bg-amber-500/10">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-amber-900 dark:text-amber-200">
        <AlertTriangle className="size-4" />
        Needs you now
        <span className="text-xs font-normal opacity-80">{total}</span>
      </div>
      <ul className="space-y-1.5 text-sm">
        {reviews_waiting.map((mr) => (
          <li key={mr.id} className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={mr.overdue ? "danger" : "info"}>{mr.overdue ? "Review overdue" : "Review"}</StatusBadge>
            <a href={mr.web_url} target="_blank" rel="noreferrer" className="font-medium hover:underline">
              {mr.title}
            </a>
            <span className="text-xs text-muted-foreground">opened {mr.days_waiting}d ago</span>
          </li>
        ))}
        {failing_pipelines.map((mr) => (
          <li key={mr.id} className="flex flex-wrap items-center gap-2">
            <StatusBadge tone="danger">Pipeline failing</StatusBadge>
            <a href={mr.web_url} target="_blank" rel="noreferrer" className="font-medium hover:underline">
              {mr.title}
            </a>
            <a href={mr.pipeline_url} target="_blank" rel="noreferrer" className="text-xs underline">
              see pipeline
            </a>
          </li>
        ))}
        {stale_items.map((item) => (
          <li key={item.id} className="flex flex-wrap items-center gap-2">
            <StatusBadge tone="warning">Stale</StatusBadge>
            <a href={item.web_url} target="_blank" rel="noreferrer" className="font-medium hover:underline">
              {item.title}
            </a>
            <span className="text-xs text-muted-foreground">no activity for {item.days_inactive}d</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
