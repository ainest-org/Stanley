"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/lib/actions-api";
import { timeAgo } from "@/lib/format";
import {
  fetchCheckIn,
  saveCheckIn,
  skipCheckIn,
  type ActivityEvent,
  type MyStats,
} from "@/lib/my-dashboard-api";

const KIND_LABEL: Record<ActivityEvent["kind"], string> = {
  merged: "Merged",
  opened: "Opened MR",
  closed: "Closed",
};

export function ActivityFeed({ events, stats }: { events: ActivityEvent[]; stats: MyStats }) {
  const [copied, setCopied] = useState(false);

  function copyWeeklySummary() {
    const lines = [
      `Weekly summary`,
      `- Merged ${stats.merged_this_week} MR(s), closed ${stats.closed_this_week} item(s) this week`,
      ...events.filter((e) => e.kind !== "opened").map((e) => `- ${KIND_LABEL[e.kind]}: ${e.title}`),
    ];
    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>Recent activity</span>
          <Button size="xs" variant="ghost" onClick={copyWeeklySummary}>
            {copied ? "Copied" : "Copy weekly summary"}
          </Button>
        </CardTitle>
        <CardDescription>Your last two weeks, straight from GitLab. Handy for 1:1 prep.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-1.5">
        {events.length === 0 && <p className="text-sm text-muted-foreground">Nothing in the last two weeks.</p>}
        {events.map((event, index) => (
          <div key={`${event.at}-${index}`} className="flex items-center gap-2 text-sm">
            <Badge variant={event.kind === "merged" ? "default" : "outline"}>{KIND_LABEL[event.kind]}</Badge>
            <a href={event.web_url} target="_blank" rel="noreferrer" className="truncate hover:underline">
              {event.title}
            </a>
            <span className="ml-auto shrink-0 text-xs text-muted-foreground">{timeAgo(event.at)}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function CheckInCard() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["check-in"], queryFn: fetchCheckIn });
  const [form, setForm] = useState({ did: "", doing: "", blockers: "" });
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!data) return;
    const source = data.saved ?? data.prefill;
    setForm({ did: source.did ?? "", doing: source.doing ?? "", blockers: source.blockers ?? "" });
  }, [data]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["check-in"] });
  const save = useMutation({
    mutationFn: () => saveCheckIn(form),
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
  });
  const skip = useMutation({ mutationFn: skipCheckIn, onSuccess: refresh });

  if (!data) return null;

  const resolved = (data.submitted || data.skipped) && !editing;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Daily check-in</CardTitle>
        <CardDescription>
          Optional. Pre-filled from your GitLab activity. Your managers can read check-ins on their Standups
          page. Skipping a day never flags anyone.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {resolved ? (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {data.submitted ? "Checked in for today." : "Skipped today."}
            </span>
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              {data.submitted ? "Edit" : "Check in anyway"}
            </Button>
          </div>
        ) : (
          <>
            {(
              [
                ["did", "What I did"],
                ["doing", "What I'm doing"],
                ["blockers", "Blockers"],
              ] as const
            ).map(([key, label]) => (
              <div key={key} className="space-y-1">
                <Label htmlFor={`checkin-${key}`}>{label}</Label>
                <Textarea
                  id={`checkin-${key}`}
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                />
              </div>
            ))}
            {(save.isError || skip.isError) && (
              <p className="text-sm text-destructive">{errorMessage(save.error ?? skip.error)}</p>
            )}
            <div className="flex gap-2">
              <Button size="sm" disabled={save.isPending} onClick={() => save.mutate()}>
                Save check-in
              </Button>
              <Button size="sm" variant="ghost" disabled={skip.isPending} onClick={() => skip.mutate()}>
                Skip today
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
