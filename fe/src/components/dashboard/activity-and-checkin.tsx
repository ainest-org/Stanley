"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { StatusBadge, type Tone } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/lib/actions-api";
import { timeAgo } from "@/lib/format";
import {
  fetchCheckIn,
  saveCheckIn,
  skipCheckIn,
  type ActivityEvent,
  type CheckInState,
  type MyStats,
} from "@/lib/my-dashboard-api";

const KIND: Record<ActivityEvent["kind"], { label: string; tone: Tone }> = {
  merged: { label: "Merged", tone: "success" },
  opened: { label: "Opened MR", tone: "info" },
  closed: { label: "Closed", tone: "neutral" },
};

export function ActivityFeed({ events, stats }: { events: ActivityEvent[]; stats: MyStats }) {
  const [copied, setCopied] = useState(false);

  function copyWeeklySummary() {
    const lines = [
      "Weekly summary",
      `- Merged ${stats.merged_this_week} MR(s), closed ${stats.closed_this_week} item(s) this week`,
      ...events.filter((e) => e.kind !== "opened").map((e) => `- ${KIND[e.kind].label}: ${e.title}`),
    ];
    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Recent activity</h3>
        <Button size="xs" variant="ghost" onClick={copyWeeklySummary}>
          {copied ? "Copied" : "Copy weekly summary"}
        </Button>
      </div>
      {events.length === 0 && <p className="text-sm text-muted-foreground">Nothing in the last two weeks.</p>}
      <ul className="space-y-1.5">
        {events.slice(0, 8).map((event, index) => (
          <li key={`${event.at}-${index}`} className="flex items-center gap-2 text-sm">
            <StatusBadge tone={KIND[event.kind].tone} className="w-20 justify-center">
              {KIND[event.kind].label}
            </StatusBadge>
            <a href={event.web_url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate hover:underline">
              {event.title}
            </a>
            <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(event.at)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** True while today's check-in is still open (not submitted, not skipped). Drives the dot on the button. */
export function useCheckInPending(): boolean {
  const { data } = useQuery({ queryKey: ["check-in"], queryFn: fetchCheckIn });
  return Boolean(data && !data.submitted && !data.skipped);
}

export function CheckInDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { data } = useQuery({ queryKey: ["check-in"], queryFn: fetchCheckIn, enabled: open });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Daily check-in</DialogTitle>
          <DialogDescription>
            Optional, and pre-filled from your GitLab activity. Your managers can read it on their Standups page.
            Skipping a day never flags anyone.
          </DialogDescription>
        </DialogHeader>
        {data ? (
          <CheckInForm data={data} onDone={() => onOpenChange(false)} />
        ) : (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function CheckInForm({ data, onDone }: { data: CheckInState; onDone: () => void }) {
  const queryClient = useQueryClient();
  const source = data.saved ?? data.prefill;
  const [form, setForm] = useState({
    did: source.did ?? "",
    doing: source.doing ?? "",
    blockers: source.blockers ?? "",
  });

  const finish = () => {
    onDone();
    queryClient.invalidateQueries({ queryKey: ["check-in"] });
  };
  const save = useMutation({ mutationFn: () => saveCheckIn(form), onSuccess: finish });
  const skip = useMutation({ mutationFn: skipCheckIn, onSuccess: finish });

  const fields = [
    ["did", "What I did"],
    ["doing", "What I'm doing"],
    ["blockers", "Blockers"],
  ] as const;

  return (
    <>
      {data.submitted && (
        <p className="text-sm text-emerald-700 dark:text-emerald-300">
          You&apos;ve already checked in today. Saving updates it.
        </p>
      )}
      {data.skipped && <p className="text-sm text-muted-foreground">You skipped today. You can still check in.</p>}

      <div className="space-y-3">
        {fields.map(([key, label]) => (
          <div key={key} className="space-y-1">
            <Label htmlFor={`checkin-${key}`}>{label}</Label>
            <Textarea
              id={`checkin-${key}`}
              rows={key === "blockers" ? 2 : 3}
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            />
          </div>
        ))}
        {(save.isError || skip.isError) && (
          <p className="text-sm text-destructive">{errorMessage(save.error ?? skip.error)}</p>
        )}
      </div>

      <DialogFooter>
        <Button variant="ghost" disabled={skip.isPending} onClick={() => skip.mutate()}>
          Skip today
        </Button>
        <Button disabled={save.isPending} onClick={() => save.mutate()}>
          Save check-in
        </Button>
      </DialogFooter>
    </>
  );
}
