"use client";

import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, XAxis } from "recharts";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { fetchRadar, type ProjectHealth } from "@/lib/dashboard-api";

const trendConfig = {
  merged_count: { label: "Merged MRs", color: "var(--chart-1)" },
  closed_count: { label: "Closed items", color: "var(--chart-2)" },
} satisfies ChartConfig;

const HEALTH_DOT: Record<ProjectHealth["status"], string> = {
  green: "bg-emerald-500",
  yellow: "bg-amber-500",
  red: "bg-destructive",
  no_active_milestone: "bg-muted-foreground/40",
};

export default function RadarPage() {
  const { data, isLoading, dataUpdatedAt } = useQuery({ queryKey: ["radar"], queryFn: fetchRadar, staleTime: 5 * 60 * 1000 });

  return (
    <AppShell>
      <div className="mb-4 flex items-baseline justify-between">
        <div>
          <h1 className="text-xl font-semibold mb-1">Exec Radar</h1>
          <p className="text-sm text-muted-foreground">What everyone is doing, in about 30 seconds.</p>
        </div>
        {dataUpdatedAt > 0 && (
          <p className="text-xs text-muted-foreground">as of {new Date(dataUpdatedAt).toLocaleTimeString()}</p>
        )}
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="In progress" value={data.summary.in_progress} />
            <StatTile label="Blocked" value={data.summary.blocked} tone="destructive" />
            <StatTile label="In review" value={data.summary.in_review} />
            <StatTile label="Shipped this week" value={data.summary.shipped_this_week} tone="positive" />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Delivery trend</CardTitle>
              <CardDescription>Merged MRs and closed items per week, last 8 weeks.</CardDescription>
            </CardHeader>
            <CardContent>
              <ChartContainer config={trendConfig} className="h-64 w-full">
                <LineChart data={data.delivery_trend}>
                  <CartesianGrid vertical={false} />
                  <XAxis
                    dataKey="week_start"
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value: string) => new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Line type="monotone" dataKey="merged_count" stroke="var(--color-merged_count)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="closed_count" stroke="var(--color-closed_count)" strokeWidth={2} dot={false} />
                </LineChart>
              </ChartContainer>
            </CardContent>
          </Card>

          <Tabs defaultValue="projects">
            <TabsList>
              <TabsTrigger value="projects">By project</TabsTrigger>
              <TabsTrigger value="people">By person</TabsTrigger>
            </TabsList>

            <TabsContent value="projects" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Per-project health</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {data.project_health.map((project) => (
                    <div key={project.project_id} className="flex items-center gap-2 text-sm">
                      <span className={`h-2.5 w-2.5 rounded-full ${HEALTH_DOT[project.status]}`} />
                      <span className="font-medium">{project.name}</span>
                      <span className="text-muted-foreground">
                        {project.milestone_title
                          ? `${project.milestone_title} · ${project.percent_done}% done`
                          : "No active milestone"}
                      </span>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Blockers</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {data.blockers.length === 0 && <p className="text-sm text-muted-foreground">Nothing blocked right now.</p>}
                  {data.blockers.map((blocker) => (
                    <div key={blocker.work_item_id} className="text-sm">
                      <a href={blocker.web_url} target="_blank" rel="noreferrer" className="font-medium hover:underline">
                        {blocker.title}
                      </a>{" "}
                      <span className="text-muted-foreground">
                        — {blocker.project_name}, blocked {blocker.blocked_days}d, {blocker.reason}
                        {blocker.assignee_name && ` (${blocker.assignee_name})`}
                      </span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="people">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">By person</CardTitle>
                  <CardDescription>Same data sliced by person, for 1:1 prep.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {data.people.map((person) => (
                    <div key={person.user_id} className="flex items-center justify-between text-sm">
                      <span className="font-medium">{person.name}</span>
                      <span className="flex gap-2">
                        <Badge variant="outline">{person.active_count} active</Badge>
                        {person.blocked_count > 0 && <Badge variant="destructive">{person.blocked_count} blocked</Badge>}
                      </span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </AppShell>
  );
}

function StatTile({ label, value, tone }: { label: string; value: number; tone?: "destructive" | "positive" }) {
  return (
    <Card>
      <CardContent className="py-4">
        <p
          className={`text-2xl font-semibold ${
            tone === "destructive" ? "text-destructive" : tone === "positive" ? "text-emerald-600 dark:text-emerald-400" : ""
          }`}
        >
          {value}
        </p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}
