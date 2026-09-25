"use client";

import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { CreateWorkItemDialog } from "@/components/dashboard/create-work-item-dialog";
import { WorkItemPanel } from "@/components/dashboard/work-item-panel";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Pick } from "@/components/ui/pick";
import { StatusBadge } from "@/components/ui/status-badge";
import { Switch } from "@/components/ui/switch";
import { fetchAllMembers } from "@/lib/actions-api";
import {
  NO_FILTERS,
  fetchBoardFilterOptions,
  fetchTeamBoard,
  type Swimlane,
  type TeamBoard,
  type TeamBoardFilters,
} from "@/lib/dashboard-api";
import { cn } from "@/lib/utils";

const ALL = "all";

export default function TeamBoardPage() {
  const [filters, setFilters] = useState<TeamBoardFilters>(NO_FILTERS);
  const [openItemId, setOpenItemId] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["team-board", filters],
    queryFn: () => fetchTeamBoard(filters),
    placeholderData: keepPreviousData,
  });
  const filterOptions = useQuery({ queryKey: ["team-board-filters"], queryFn: fetchBoardFilterOptions });
  const members = useQuery({ queryKey: ["members"], queryFn: fetchAllMembers }).data ?? [];

  return (
    <AppShell>
      <PageHeader
        title="Team Board"
        description="One lane per person. Click any item to see it, reassign it or comment."
      />

      <FilterBar filters={filters} onChange={setFilters} options={filterOptions.data} />

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {data && (
        <div className="space-y-4">
          <AttentionCard board={data} onOpenItem={setOpenItemId} />

          <div className="space-y-3">
            {data.swimlanes.map((lane) => (
              <Lane key={lane.user_id} lane={lane} onOpenItem={setOpenItemId} />
            ))}
            {data.swimlanes.length === 0 && (
              <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                Nothing matches these filters.
              </p>
            )}
          </div>
        </div>
      )}

      <WorkItemPanel itemId={openItemId} onClose={() => setOpenItemId(null)} members={members} />
    </AppShell>
  );
}

function FilterBar({
  filters,
  onChange,
  options,
}: {
  filters: TeamBoardFilters;
  onChange: (next: TeamBoardFilters) => void;
  options: { projects: { id: string; name: string }[]; milestones: string[]; labels: string[] } | undefined;
}) {
  const active = JSON.stringify(filters) !== JSON.stringify(NO_FILTERS);

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <Pick
        className="w-44"
        value={filters.projectId ?? ALL}
        onChange={(v) => onChange({ ...filters, projectId: v === ALL ? null : v })}
        options={[{ value: ALL, label: "All projects" }, ...(options?.projects ?? []).map((p) => ({ value: p.id, label: p.name }))]}
        placeholder="Project"
      />
      <Pick
        className="w-40"
        value={filters.milestone ?? ALL}
        onChange={(v) => onChange({ ...filters, milestone: v === ALL ? null : v })}
        options={[{ value: ALL, label: "All milestones" }, ...(options?.milestones ?? []).map((m) => ({ value: m, label: m }))]}
        placeholder="Milestone"
      />
      <Pick
        className="w-36"
        value={filters.label ?? ALL}
        onChange={(v) => onChange({ ...filters, label: v === ALL ? null : v })}
        options={[{ value: ALL, label: "All labels" }, ...(options?.labels ?? []).map((l) => ({ value: l, label: l }))]}
        placeholder="Label"
      />
      <div className="flex items-center gap-2 pl-1">
        <Switch
          id="flagged-only"
          checked={filters.flaggedOnly}
          onCheckedChange={(checked) => onChange({ ...filters, flaggedOnly: checked })}
        />
        <Label htmlFor="flagged-only" className="text-sm">
          Flagged only
        </Label>
      </div>
      {active && (
        <Button size="sm" variant="ghost" onClick={() => onChange(NO_FILTERS)}>
          Clear
        </Button>
      )}
    </div>
  );
}

function AttentionRow({ label, tone, children }: { label: string; tone: "danger" | "warning" | "info" | "neutral"; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1.5">
      <StatusBadge tone={tone} className="w-28 justify-center">
        {label}
      </StatusBadge>
      <div className="flex min-w-0 flex-1 flex-wrap gap-x-4 gap-y-1 text-sm">{children}</div>
    </div>
  );
}

function AttentionCard({ board, onOpenItem }: { board: TeamBoard; onOpenItem: (id: string) => void }) {
  const { stalled_mrs, unassigned_items, reviews_pending_sla, idle_engineers, overloaded_engineers } = board.attention;
  const total =
    stalled_mrs.length +
    unassigned_items.length +
    reviews_pending_sla.length +
    idle_engineers.length +
    overloaded_engineers.length;
  if (total === 0) return null;

  return (
    <div className="space-y-3 rounded-xl border border-amber-300/60 bg-amber-50 p-4 dark:border-amber-500/30 dark:bg-amber-500/10">
      <div className="flex items-center gap-2 text-sm font-medium text-amber-900 dark:text-amber-200">
        <AlertTriangle className="size-4" />
        Needs your attention
        <span className="text-xs font-normal opacity-80">{total}</span>
      </div>

      {unassigned_items.length > 0 && (
        <AttentionRow label="Unassigned" tone="warning">
          {unassigned_items.map((item) => (
            <button key={item.id} type="button" className="text-left font-medium hover:underline" onClick={() => onOpenItem(item.id)}>
              {item.title}
            </button>
          ))}
        </AttentionRow>
      )}
      {reviews_pending_sla.length > 0 && (
        <AttentionRow label="Review overdue" tone="danger">
          {reviews_pending_sla.map((mr) => (
            <a key={`${mr.id}-${mr.reviewer_name}`} href={mr.web_url} target="_blank" rel="noreferrer" className="hover:underline">
              <span className="font-medium">{mr.title}</span>
              <span className="text-muted-foreground"> · {mr.reviewer_name}, {mr.days_pending}d</span>
            </a>
          ))}
        </AttentionRow>
      )}
      {stalled_mrs.length > 0 && (
        <AttentionRow label="Stalled MRs" tone="warning">
          {stalled_mrs.map((mr) => (
            <a key={mr.id} href={mr.web_url} target="_blank" rel="noreferrer" className="hover:underline">
              <span className="font-medium">{mr.title}</span>
              <span className="text-muted-foreground"> · {mr.days_inactive}d quiet</span>
            </a>
          ))}
        </AttentionRow>
      )}
      {overloaded_engineers.length > 0 && (
        <AttentionRow label="Overloaded" tone="danger">
          {overloaded_engineers.map((p) => (
            <span key={p.user_id}>
              <span className="font-medium">{p.name}</span>
              <span className="text-muted-foreground"> · {p.active_count} active</span>
            </span>
          ))}
        </AttentionRow>
      )}
      {idle_engineers.length > 0 && (
        <AttentionRow label="Idle" tone="neutral">
          {idle_engineers.map((p) => (
            <span key={p.user_id} className="font-medium">
              {p.name}
            </span>
          ))}
        </AttentionRow>
      )}
    </div>
  );
}

const MAX_SHOWN = 3;

function Lane({ lane, onOpenItem }: { lane: Swimlane; onOpenItem: (id: string) => void }) {
  const hidden = lane.active_count - lane.items.length;

  return (
    <div className="grid gap-3 rounded-xl border bg-card p-4 shadow-xs md:grid-cols-[15rem_1fr]">
      <div className="flex items-start gap-3">
        <Avatar className="size-9">
          <AvatarImage src={lane.avatar_url ?? undefined} alt={lane.name} />
          <AvatarFallback>{lane.name.slice(0, 1)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 space-y-1.5">
          <p className="truncate text-sm font-semibold leading-tight">{lane.name}</p>
          <div className="flex flex-wrap gap-1">
            <StatusBadge>{lane.active_count} active</StatusBadge>
            {lane.blocked_count > 0 && <StatusBadge tone="danger">{lane.blocked_count} blocked</StatusBadge>}
            {lane.stale_count > 0 && <StatusBadge tone="warning">{lane.stale_count} stale</StatusBadge>}
          </div>
        </div>
      </div>

      <div className="min-w-0 space-y-1">
        {lane.items.length === 0 && <p className="py-1.5 text-sm text-muted-foreground">No active items.</p>}
        {lane.items.slice(0, MAX_SHOWN).map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onOpenItem(item.id)}
            className="flex w-full items-center gap-3 rounded-lg px-2.5 py-1.5 text-left text-sm hover:bg-muted"
          >
            <span
              className={cn(
                "size-2 shrink-0 rounded-full",
                item.is_blocked ? "bg-red-500" : item.is_stale || item.is_flagged ? "bg-amber-400" : "bg-slate-300 dark:bg-slate-600",
              )}
            />
            <span className="min-w-0 flex-1 truncate font-medium">{item.title}</span>
            {item.is_blocked && <StatusBadge tone="danger">Blocked</StatusBadge>}
            {!item.is_blocked && item.is_stale && <StatusBadge tone="warning">Stale</StatusBadge>}
            <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">{item.project_name}</span>
          </button>
        ))}
        <div className="flex items-center gap-3 px-1.5 pt-0.5">
          {hidden > 0 && <span className="text-xs text-muted-foreground">+{hidden} more</span>}
          <CreateWorkItemDialog
            defaultAssigneeId={lane.user_id}
            triggerLabel={`+ Add for ${lane.name.split(" ")[0]}`}
            triggerVariant="ghost"
            triggerSize="xs"
          />
        </div>
      </div>
    </div>
  );
}
