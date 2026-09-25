"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type MyAttention } from "@/lib/my-dashboard-api";

export function MyAttentionStrip({ attention }: { attention: MyAttention }) {
  const { reviews_waiting, failing_pipelines, stale_items } = attention;
  if (reviews_waiting.length + failing_pipelines.length + stale_items.length === 0) return null;

  return (
    <Card className="border-amber-400/50">
      <CardHeader>
        <CardTitle className="text-base">Needs you now</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {reviews_waiting.map((mr) => (
          <div key={mr.id} className="flex flex-wrap items-center gap-2">
            <Badge variant={mr.overdue ? "destructive" : "outline"}>{mr.overdue ? "Review overdue" : "Review"}</Badge>
            <a href={mr.web_url} target="_blank" rel="noreferrer" className="hover:underline">
              {mr.title}
            </a>
            <span className="text-xs text-muted-foreground">opened {mr.days_waiting}d ago</span>
          </div>
        ))}
        {failing_pipelines.map((mr) => (
          <div key={mr.id} className="flex flex-wrap items-center gap-2">
            <Badge variant="destructive">Pipeline failing</Badge>
            <a href={mr.web_url} target="_blank" rel="noreferrer" className="hover:underline">
              {mr.title}
            </a>
            <a href={mr.pipeline_url} target="_blank" rel="noreferrer" className="text-xs underline">
              see pipeline
            </a>
          </div>
        ))}
        {stale_items.map((item) => (
          <div key={item.id} className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">Stale</Badge>
            <a href={item.web_url} target="_blank" rel="noreferrer" className="hover:underline">
              {item.title}
            </a>
            <span className="text-xs text-muted-foreground">no activity for {item.days_inactive}d</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
