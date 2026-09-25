"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, ClipboardCheck, Inbox, Search } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { WorkCard } from "@/components/dashboard/work-card";
import { WorkItemPanel } from "@/components/dashboard/work-item-panel";
import { MyStatsBar, MyTrendChart } from "@/components/dashboard/my-stats";
import { MyAttentionStrip } from "@/components/dashboard/my-attention";
import { TodosSheet, useTodoCount } from "@/components/dashboard/todos-panel";
import { ActivityFeed, CheckInDialog, useCheckInPending } from "@/components/dashboard/activity-and-checkin";
import { Pick } from "@/components/ui/pick";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fetchAllMembers } from "@/lib/actions-api";
import { fetchMyWork, type MyWork, type WorkCard as WorkCardData } from "@/lib/dashboard-api";
import { fetchMyOverview } from "@/lib/my-dashboard-api";
import { cn } from "@/lib/utils";

const COLUMNS: { key: keyof MyWork; label: string; dot: string; empty: string; hint: string }[] = [
  {
    key: "doing_now",
    label: "Doing now",
    dot: "bg-indigo-500",
    empty: "Nothing in progress. A draft MR or the in-progress label puts an item here.",
    hint: "Your draft or failing MR, or the in-progress label",
  },
  { key: "up_next", label: "Up next", dot: "bg-slate-400", empty: "You're all caught up.", hint: "Assigned to you, not started" },
  {
    key: "waiting_on_others",
    label: "Waiting on others",
    dot: "bg-amber-500",
    empty: "Nothing is waiting on someone else.",
    hint: "Your MR is ready for review, or the item is blocked",
  },
  {
    key: "review_requests",
    label: "Review requests",
    dot: "bg-sky-500",
    empty: "No reviews requested from you.",
    hint: "Merge requests where you're a reviewer",
  },
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

function Column({
  label,
  dot,
  hint,
  empty,
  cards,
  queryKey,
  onOpen,
}: {
  label: string;
  dot: string;
  hint: string;
  empty: string;
  cards: WorkCardData[];
  queryKey: unknown[];
  onOpen: (id: string) => void;
}) {
  return (
    <section className="flex min-w-0 flex-col rounded-xl bg-muted/70 p-2">
      <header className="flex items-center gap-2 px-2 py-1.5" title={hint}>
        <span className={cn("size-2 rounded-full", dot)} />
        <h2 className="text-sm font-semibold">{label}</h2>
        <span className="rounded-full bg-background px-2 py-0.5 text-xs font-medium text-muted-foreground">
          {cards.length}
        </span>
      </header>
      <div className="max-h-[68vh] space-y-2 overflow-y-auto p-0.5">
        {cards.length === 0 && <p className="px-2 py-4 text-center text-xs text-muted-foreground">{empty}</p>}
        {cards.map((card) => (
          <WorkCard key={card.id} card={card} queryKey={queryKey} onOpen={onOpen} />
        ))}
      </div>
    </section>
  );
}

export default function MyWorkPage() {
  const queryKey = ["my-work"];
  const { data, isLoading } = useQuery({ queryKey, queryFn: fetchMyWork });
  const overview = useQuery({ queryKey: ["my-work", "overview"], queryFn: fetchMyOverview });
  const members = useQuery({ queryKey: ["members"], queryFn: fetchAllMembers }).data ?? [];
  const todoCount = useTodoCount();
  const checkInPending = useCheckInPending();

  const [openItemId, setOpenItemId] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [showTrends, setShowTrends] = useState(false);
  const [inboxOpen, setInboxOpen] = useState(false);
  const [checkInOpen, setCheckInOpen] = useState(false);

  const allCards = useMemo(
    () => (data ? [...COLUMNS.flatMap((c) => data[c.key] as WorkCardData[]), ...data.watching, ...data.snoozed] : []),
    [data],
  );
  const projects = useMemo(() => [...new Set(allCards.map((c) => c.project_name))].sort(), [allCards]);
  const labels = useMemo(() => [...new Set(allCards.flatMap((c) => c.labels))].sort(), [allCards]);
  const filtersActive = JSON.stringify(filters) !== JSON.stringify(NO_FILTERS);

  const filtered = (cards: WorkCardData[]) => cards.filter((c) => matches(c, filters));

  return (
    <AppShell>
      <PageHeader
        title="My Work"
        description="Inferred from GitLab, so there's no status to set by hand."
        actions={
          <>
            <Button variant="outline" onClick={() => setCheckInOpen(true)} className="relative">
              <ClipboardCheck className="size-4" /> Check-in
              {checkInPending && <span className="absolute -right-1 -top-1 size-2.5 rounded-full bg-amber-500 ring-2 ring-background" />}
            </Button>
            <Button variant="outline" onClick={() => setInboxOpen(true)}>
              <Inbox className="size-4" /> Inbox
              {todoCount > 0 && (
                <span className="rounded-full bg-primary px-1.5 text-[11px] font-semibold text-primary-foreground">
                  {todoCount}
                </span>
              )}
            </Button>
          </>
        }
      />

      <div className="space-y-4">
        {overview.data && <MyStatsBar stats={overview.data.stats} />}

        {overview.data && (
          <div>
            <Button size="sm" variant="ghost" onClick={() => setShowTrends(!showTrends)}>
              <BarChart3 className="size-4" /> {showTrends ? "Hide" : "Show"} trends and activity
            </Button>
            {showTrends && (
              <div className="mt-2 grid gap-6 rounded-xl border bg-card p-4 shadow-xs lg:grid-cols-2">
                <div className="space-y-2">
                  <h3 className="text-sm font-medium">Your last 8 weeks</h3>
                  <p className="text-xs text-muted-foreground">Only you see this. Counts and ages, never hours or points.</p>
                  <MyTrendChart stats={overview.data.stats} />
                </div>
                <ActivityFeed events={overview.data.activity} stats={overview.data.stats} />
              </div>
            )}
          </div>
        )}

        {overview.data && <MyAttentionStrip attention={overview.data.attention} />}

        <Tabs defaultValue="board">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <TabsList>
              <TabsTrigger value="board">Board</TabsTrigger>
              <TabsTrigger value="watching">Watching{data ? ` (${data.watching.length})` : ""}</TabsTrigger>
              <TabsTrigger value="snoozed">Snoozed{data ? ` (${data.snoozed.length})` : ""}</TabsTrigger>
            </TabsList>

            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
                <Input
                  className="w-52 pl-8"
                  placeholder="Search…"
                  value={filters.search}
                  onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                />
              </div>
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
                  Flagged
                </Label>
              </div>
              {filtersActive && (
                <Button size="sm" variant="ghost" onClick={() => setFilters(NO_FILTERS)}>
                  Clear
                </Button>
              )}
            </div>
          </div>

          {isLoading && <p className="mt-4 text-sm text-muted-foreground">Loading…</p>}

          {data && (
            <>
              <TabsContent value="board" className="mt-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                  {COLUMNS.map((column) => (
                    <Column
                      key={column.key}
                      label={column.label}
                      dot={column.dot}
                      hint={column.hint}
                      empty={filtersActive ? "Nothing matches your filters." : column.empty}
                      cards={filtered(data[column.key] as WorkCardData[])}
                      queryKey={queryKey}
                      onOpen={setOpenItemId}
                    />
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="watching" className="mt-4">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {filtered(data.watching).map((card) => (
                    <WorkCard key={card.id} card={card} queryKey={queryKey} onOpen={setOpenItemId} />
                  ))}
                </div>
                {filtered(data.watching).length === 0 && (
                  <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                    Nothing here yet. Use the menu on any card and choose Watch to follow an item you don&apos;t own.
                  </p>
                )}
              </TabsContent>

              <TabsContent value="snoozed" className="mt-4">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {filtered(data.snoozed).map((card) => (
                    <WorkCard key={card.id} card={card} queryKey={queryKey} onOpen={setOpenItemId} />
                  ))}
                </div>
                {filtered(data.snoozed).length === 0 && (
                  <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                    No snoozed items. Snooze hides a card until the date you pick.
                  </p>
                )}
              </TabsContent>
            </>
          )}
        </Tabs>
      </div>

      <TodosSheet open={inboxOpen} onOpenChange={setInboxOpen} onOpenItem={setOpenItemId} />
      <CheckInDialog open={checkInOpen} onOpenChange={setCheckInOpen} />
      <WorkItemPanel itemId={openItemId} onClose={() => setOpenItemId(null)} members={members} />
    </AppShell>
  );
}
