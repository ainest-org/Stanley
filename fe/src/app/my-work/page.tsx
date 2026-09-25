"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { WorkCard } from "@/components/dashboard/work-card";
import { fetchMyWork, type WorkCard as WorkCardData } from "@/lib/dashboard-api";

const COLUMNS: { key: keyof Awaited<ReturnType<typeof fetchMyWork>>; label: string }[] = [
  { key: "doing_now", label: "Doing now" },
  { key: "up_next", label: "Up next" },
  { key: "waiting_on_others", label: "Waiting on someone else" },
  { key: "review_requests", label: "Review requests" },
];

export default function MyWorkPage() {
  const queryKey = ["my-work"];
  const { data, isLoading } = useQuery({ queryKey, queryFn: fetchMyWork });

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold mb-1">My Work</h1>
        <p className="text-sm text-muted-foreground">
          Always inferred from GitLab — there&apos;s no manual status to set here.
        </p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((column) => {
            const cards = data[column.key] as WorkCardData[];
            return (
              <div key={column.key} className="space-y-2">
                <div className="flex items-center justify-between px-1">
                  <h2 className="text-sm font-medium">{column.label}</h2>
                  <span className="text-xs text-muted-foreground">{cards.length}</span>
                </div>
                <div className="space-y-2">
                  {cards.length === 0 && (
                    <p className="px-1 text-xs text-muted-foreground">Nothing here.</p>
                  )}
                  {cards.map((card) => (
                    <WorkCard key={card.id} card={card} queryKey={queryKey} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
