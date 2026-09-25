"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, GitPullRequest, OctagonAlert, Rocket } from "lucide-react";
import { CartesianGrid, Line, LineChart, XAxis } from "recharts";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { StatusBadge, type Tone } from "@/components/ui/status-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { fetchRadar, type ProjectHealth } from "@/lib/dashboard-api";
import { cn } from "@/lib/utils";

const trendConfig = {
  merged_count: { label: "Merged MRs", color: "var(--chart-1)" },
  closed_count: { label: "Closed items", color: "var(--chart-2)" },
} satisfies ChartConfig;

const HEALTH: Record<ProjectHealth["status"], { label: string; tone: Tone; bar: string }> = {
  green: { label: "On track", tone: "success", bar: "bg-emerald-500" },
  yellow: { label: "At risk", tone: "warning", bar: "bg-amber-500" },
  red: { label: "Behind", tone: "danger", bar: "bg-red-500" },
  no_active_milestone: { label: "No active milestone", tone: "neutral", bar: "bg-slate-300" },
};

function Kpi({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}) {
  return (
    <div className="flex items-center gap-4 rounded-xl border bg-card p-4 shadow-xs">
      <span className={cn("flex size-11 items-center justify-center rounded-lg", accent)}>
        <Icon className="size-5" />
      </span>
      <div>
        <p className="text-3xl font-semibold tracking-tight">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

export default function RadarPage() {
  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ["radar"],
    queryFn: fetchRadar,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <AppShell>
      <PageHeader
        title="Exec Radar"
        description="What everyone is doing and what's stuck, in about 30 seconds."
        actions={
          dataUpdatedAt > 0 ? (
            <span className="text-xs text-muted-foreground">as of {new Date(dataUpdatedAt).toLocaleTimeString()}</span>
          ) : undefined
        }
      />

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <Kpi label="In progress" value={data.summary.in_progress} icon={GitPullRequest} accent="bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-200" />
            <Kpi label="Blocked" value={data.summary.blocked} icon={OctagonAlert} accent="bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-200" />
            <Kpi label="In review" value={data.summary.in_review} icon={CheckCircle2} accent="bg-sky-100 text-sky-700 dark:bg-sky-500/20 dark:text-sky-200" />
            <Kpi label="Shipped this week" value={data.summary.shipped_this_week} icon={Rocket} accent="bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200" />
          </div>

          <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
            <section className="rounded-xl border bg-card p-4 shadow-xs">
              <h2 className="text-sm font-semibold">Delivery trend</h2>
              <p className="mb-2 text-xs text-muted-foreground">Merged MRs and closed items per week, last 8 weeks.</p>
              <ChartContainer config={trendConfig} className="h-64 w-full">
                <LineChart data={data.delivery_trend}>
                  <CartesianGrid vertical={false} />
                  <XAxis
                    dataKey="week_start"
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value: string) =>
                      new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" })
                    }
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Line type="monotone" dataKey="merged_count" stroke="var(--color-merged_count)" strokeWidth={2.5} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="closed_count" stroke="var(--color-closed_count)" strokeWidth={2.5} dot={{ r: 3 }} />
                </LineChart>
              </ChartContainer>
            </section>

            <section className="rounded-xl border bg-card p-4 shadow-xs">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold">What&apos;s stuck</h2>
                <StatusBadge tone={data.blockers.length > 0 ? "danger" : "success"}>{data.blockers.length} blocked</StatusBadge>
              </div>
              {data.blockers.length === 0 && (
                <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                  Nothing is blocked right now.
                </p>
              )}
              <ul className="space-y-3">
                {data.blockers.map((blocker) => (
                  <li key={blocker.work_item_id} className="space-y-0.5 border-l-2 border-red-400 pl-3">
                    <a href={blocker.web_url} target="_blank" rel="noreferrer" className="text-sm font-medium hover:underline">
                      {blocker.title}
                    </a>
                    <p className="text-sm text-muted-foreground">{blocker.reason}</p>
                    <p className="text-xs text-muted-foreground">
                      {blocker.project_name} · {blocker.blocked_days === 0 ? "since today" : `${blocker.blocked_days}d`}
                      {blocker.assignee_name && ` · ${blocker.assignee_name}`}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <Tabs defaultValue="projects">
            <TabsList>
              <TabsTrigger value="projects">By project</TabsTrigger>
              <TabsTrigger value="people">By person</TabsTrigger>
            </TabsList>

            <TabsContent value="projects" className="mt-4">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {data.project_health.map((project) => {
                  const health = HEALTH[project.status];
                  return (
                    <div key={project.project_id} className="space-y-3 rounded-xl border bg-card p-4 shadow-xs">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold">{project.name}</p>
                          <p className="text-xs text-muted-foreground">{project.milestone_title ?? "No active milestone"}</p>
                        </div>
                        <StatusBadge tone={health.tone}>{health.label}</StatusBadge>
                      </div>
                      {project.percent_done !== null && (
                        <div className="space-y-1">
                          <div className="h-2 overflow-hidden rounded-full bg-muted">
                            <div className={cn("h-full rounded-full", health.bar)} style={{ width: `${project.percent_done}%` }} />
                          </div>
                          <p className="text-xs text-muted-foreground">{project.percent_done}% of milestone items done</p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </TabsContent>

            <TabsContent value="people" className="mt-4">
              <div className="overflow-hidden rounded-xl border bg-card shadow-xs">
                <table className="w-full text-sm">
                  <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="px-4 py-2 font-medium">Person</th>
                      <th className="px-4 py-2 font-medium">Active items</th>
                      <th className="px-4 py-2 font-medium">Blocked</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {data.people.map((person) => (
                      <tr key={person.user_id}>
                        <td className="px-4 py-2.5 font-medium">{person.name}</td>
                        <td className="px-4 py-2.5">{person.active_count}</td>
                        <td className="px-4 py-2.5">
                          {person.blocked_count > 0 ? (
                            <StatusBadge tone="danger">{person.blocked_count}</StatusBadge>
                          ) : (
                            <span className="text-muted-foreground">0</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </AppShell>
  );
}
