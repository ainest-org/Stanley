"use client";

import { Bar, BarChart, CartesianGrid, XAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { type MyStats } from "@/lib/my-dashboard-api";

const chartConfig = {
  merged: { label: "MRs merged", color: "var(--chart-1)" },
  closed: { label: "Items closed", color: "var(--chart-2)" },
} satisfies ChartConfig;

function Cell({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="px-4 py-3">
      <p className="text-xl font-semibold tracking-tight">{value}</p>
      <p className="text-xs font-medium text-foreground/80">{label}</p>
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** One slim row of the numbers that matter. Only the signed-in person sees these. */
export function MyStatsBar({ stats }: { stats: MyStats }) {
  const delta = stats.merged_this_week - stats.merged_last_week;
  return (
    <div className="grid grid-cols-2 divide-x divide-y overflow-hidden rounded-xl border bg-card shadow-xs sm:grid-cols-3 lg:grid-cols-6 lg:divide-y-0">
      <Cell
        label="MRs merged this week"
        value={String(stats.merged_this_week)}
        hint={`${delta >= 0 ? "+" : ""}${delta} vs last week`}
      />
      <Cell label="Items closed this week" value={String(stats.closed_this_week)} />
      <Cell
        label="Median MR cycle time"
        value={stats.median_cycle_days === null ? "n/a" : `${stats.median_cycle_days}d`}
        hint="opened to merged, 90 days"
      />
      <Cell
        label="MRs with passing pipeline"
        value={stats.pipeline_pass_rate === null ? "n/a" : `${stats.pipeline_pass_rate}%`}
        hint="open + merged, 30 days"
      />
      <Cell
        label="Reviews waiting on you"
        value={String(stats.reviews_waiting)}
        hint={
          stats.oldest_review_waiting_days === null
            ? `${stats.reviews_approved_recent} approved recently`
            : `oldest opened ${stats.oldest_review_waiting_days}d ago`
        }
      />
      <Cell
        label="Open items assigned"
        value={String(stats.open_items)}
        hint={stats.oldest_open_item_days === null ? undefined : `oldest is ${stats.oldest_open_item_days}d old`}
      />
    </div>
  );
}

export function MyTrendChart({ stats }: { stats: MyStats }) {
  return (
    <ChartContainer config={chartConfig} className="h-44 w-full">
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
        <Bar dataKey="merged" fill="var(--color-merged)" radius={4} />
        <Bar dataKey="closed" fill="var(--color-closed)" radius={4} />
      </BarChart>
    </ChartContainer>
  );
}
