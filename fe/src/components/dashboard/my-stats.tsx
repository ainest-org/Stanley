"use client";

import { Bar, BarChart, CartesianGrid, XAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { type MyStats } from "@/lib/my-dashboard-api";

const chartConfig = {
  merged: { label: "MRs merged", color: "var(--chart-1)" },
  closed: { label: "Items closed", color: "var(--chart-2)" },
} satisfies ChartConfig;

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardContent className="py-3">
        <p className="text-2xl font-semibold">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
        {hint && <p className="mt-0.5 text-xs text-muted-foreground/80">{hint}</p>}
      </CardContent>
    </Card>
  );
}

export function MyStatsStrip({ stats }: { stats: MyStats }) {
  const delta = stats.merged_this_week - stats.merged_last_week;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Tile
          label="MRs merged this week"
          value={String(stats.merged_this_week)}
          hint={`${delta >= 0 ? "+" : ""}${delta} vs last week`}
        />
        <Tile label="Items closed this week" value={String(stats.closed_this_week)} />
        <Tile
          label="Median MR cycle time"
          value={stats.median_cycle_days === null ? "n/a" : `${stats.median_cycle_days}d`}
          hint="opened to merged, last 90 days"
        />
        <Tile
          label="MRs with passing pipeline"
          value={stats.pipeline_pass_rate === null ? "n/a" : `${stats.pipeline_pass_rate}%`}
          hint="open + merged in last 30 days"
        />
        <Tile
          label="Waiting on your review"
          value={String(stats.reviews_waiting)}
          hint={
            stats.oldest_review_waiting_days === null
              ? `${stats.reviews_approved_recent} approved recently`
              : `oldest opened ${stats.oldest_review_waiting_days}d ago`
          }
        />
        <Tile
          label="Open items assigned"
          value={String(stats.open_items)}
          hint={stats.oldest_open_item_days === null ? undefined : `oldest is ${stats.oldest_open_item_days}d old`}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Your last 8 weeks</CardTitle>
          <CardDescription>Only you see this. Counts and ages, never hours or points.</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={chartConfig} className="h-40 w-full">
            <BarChart data={stats.trend}>
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
              <Bar dataKey="merged" fill="var(--color-merged)" radius={3} />
              <Bar dataKey="closed" fill="var(--color-closed)" radius={3} />
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </div>
  );
}
