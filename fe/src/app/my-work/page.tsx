"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { WorkCard } from "@/components/dashboard/work-card";
import { WorkItemPanel } from "@/components/dashboard/work-item-panel";
import { MyStatsStrip } from "@/components/dashboard/my-stats";
import { MyAttentionStrip } from "@/components/dashboard/my-attention";
import { TodosPanel } from "@/components/dashboard/todos-panel";
import { ActivityFeed, CheckInCard } from "@/components/dashboard/activity-and-checkin";
import { Pick } from "@/components/ui/pick";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { fetchAllMembers } from "@/lib/actions-api";
import { fetchMyWork, type MyWork, type WorkCard as WorkCardData } from "@/lib/dashboard-api";
import { fetchMyOverview } from "@/lib/my-dashboard-api";

const COLUMNS: { key: keyof MyWork; label: string; hint?: string }[] = [
  { key: "doing_now", label: "Doing now", hint: "Draft or failing MR, or the in-progress label" },
  { key: "up_next", label: "Up next" },
  { key: "waiting_on_others", label: "Waiting on someone else" },
  { key: "review_requests", label: "Review requests" },
  { key: "watching", label: "Watching" },
];

const ALL = "all";

interface Filters {
  search: string;
  project: string;
  label: string;
  flaggedOnly: boolean;
}

const NO_FILTERS: Filters = { search: "", project: ALL, label: ALL, flaggedOnly: false };

function matches(card: WorkCardData, filters: Filters): boolean {
  if (filters.project !== ALL && card.project_name !== filters.project) return false;
  if (filters.label !== ALL && !card.labels.includes(filters.label)) return false;
  if (filters.flaggedOnly && !card.is_flagged) return false;
  const term = filters.search.trim().toLowerCase();
  if (term && !`${card.title} ${card.project_name} ${card.labels.join(" ")}`.toLowerCase().includes(term)) return false;
  return true;
}

export default function MyWorkPage() {
  const queryKey = ["my-work"];
  const { data, isLoading } = useQuery({ queryKey, queryFn: fetchMyWork });
  const overview = useQuery({ queryKey: ["my-work", "overview"], queryFn: fetchMyOverview });
  const members = useQuery({ queryKey: ["members"], queryFn: fetchAllMembers }).data ?? [];
  const [openItemId, setOpenItemId] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [showSnoozed, setShowSnoozed] = useState(false);

  const allCards = useMemo(
    () => (data ? COLUMNS.flatMap((c) => data[c.key] as WorkCardData[]).concat(data.snoozed) : []),
    [data],
  );
  const projects = useMemo(() => [...new Set(allCards.map((c) => c.project_name))].sort(), [allCards]);
  const labels = useMemo(() => [...new Set(allCards.flatMap((c) => c.labels))].sort(), [allCards]);
  const filtersActive = JSON.stringify(filters) !== JSON.stringify(NO_FILTERS);

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold mb-1">My Work</h1>
        <p className="text-sm text-muted-foreground">
          Always inferred from GitLab. There&apos;s no manual status to set here.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
        <div className="min-w-0 space-y-4">
          {overview.data && <MyStatsStrip stats={overview.data.stats} />}
          {overview.data && <MyAttentionStrip attention={overview.data.attention} />}

          <div className="flex flex-wrap items-center gap-3">
            <Input
              className="w-56"
              placeholder="Search my work…"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            />
            <Pick
              className="w-40"
              value={filters.project}
              onChange={(project) => setFilters({ ...filters, project })}
              options={[{ value: ALL, label: "All projects" }, ...projects.map((p) => ({ value: p, label: p }))]}
              placeholder="Project"
            />
            <Pick
              className="w-36"
              value={filters.label}
              onChange={(label) => setFilters({ ...filters, label })}
              options={[{ value: ALL, label: "All labels" }, ...labels.map((l) => ({ value: l, label: l }))]}
              placeholder="Label"
            />
            <div className="flex items-center gap-2">
              <Switch
                id="my-flagged"
                checked={filters.flaggedOnly}
                onCheckedChange={(flaggedOnly) => setFilters({ ...filters, flaggedOnly })}
              />
              <Label htmlFor="my-flagged" className="text-sm">
                Flagged only
              </Label>
            </div>
            {filtersActive && (
              <Button size="sm" variant="ghost" onClick={() => setFilters(NO_FILTERS)}>
                Clear
              </Button>
            )}
          </div>

          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

          {data && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {COLUMNS.map((column) => {
                const cards = (data[column.key] as WorkCardData[]).filter((c) => matches(c, filters));
                return (
                  <div key={column.key} className="space-y-2">
                    <div className="flex items-center justify-between px-1">
                      <h2 className="text-sm font-medium" title={column.hint}>
                        {column.label}
                      </h2>
                      <span className="text-xs text-muted-foreground">{cards.length}</span>
                    </div>
                    <div className="space-y-2">
                      {cards.length === 0 && <p className="px-1 text-xs text-muted-foreground">Nothing here.</p>}
                      {cards.map((card) => (
                        <WorkCard key={card.id} card={card} queryKey={queryKey} onOpen={setOpenItemId} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {data && data.snoozed.length > 0 && (
            <div className="space-y-2">
              <Button size="sm" variant="ghost" onClick={() => setShowSnoozed(!showSnoozed)}>
                {showSnoozed ? "Hide" : "Show"} snoozed ({data.snoozed.length})
              </Button>
              {showSnoozed && (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 2xl:grid-cols-3">
                  {data.snoozed
                    .filter((c) => matches(c, filters))
                    .map((card) => (
                      <WorkCard key={card.id} card={card} queryKey={queryKey} onOpen={setOpenItemId} />
                    ))}
                </div>
              )}
            </div>
          )}
        </div>

        <aside className="min-w-0 space-y-4">
          <TodosPanel onOpenItem={setOpenItemId} />
          <CheckInCard />
          {overview.data && <ActivityFeed events={overview.data.activity} stats={overview.data.stats} />}
        </aside>
      </div>

      <WorkItemPanel itemId={openItemId} onClose={() => setOpenItemId(null)} members={members} />
    </AppShell>
  );
}
