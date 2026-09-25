"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchOrgSettings, updateOrgSettings, type OrgSettings } from "@/lib/admin-api";

const FIELDS: { key: keyof OrgSettings; label: string; help: string }[] = [
  {
    key: "stale_threshold_days",
    label: "Stale after (days)",
    help: "No activity for this long flags an item as stale.",
  },
  {
    key: "stale_recheck_days",
    label: "Stale re-check every (days)",
    help: "Frequent, gentle nudge — stale items usually just need a poke.",
  },
  {
    key: "blocked_recheck_days",
    label: "Blocked re-alert every (days)",
    help: "Infrequent by design — pinging more often rarely unblocks a real blocker.",
  },
  {
    key: "review_sla_days",
    label: "Review SLA (days)",
    help: "Reviews pending longer than this show up on the Team Board's attention strip.",
  },
  {
    key: "overloaded_item_threshold",
    label: "Overloaded at (active items)",
    help: "Flags an engineer as overloaded above this many active items.",
  },
];

export function HealthThresholds() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["org-settings"], queryFn: fetchOrgSettings });
  const [form, setForm] = useState<OrgSettings | null>(null);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const mutation = useMutation({
    mutationFn: (patch: Partial<OrgSettings>) => updateOrgSettings(patch),
    onSuccess: (updated) => {
      setForm(updated);
      queryClient.setQueryData(["org-settings"], updated);
    },
  });

  if (!form) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Health-rule thresholds</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading…</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Health-rule thresholds</CardTitle>
        <CardDescription>
          Two-speed by design: stale items re-surface often since they&apos;re usually just idle;
          blocked items re-alert rarely since a real blocker isn&apos;t solved by pinging more.
          Set once here — per-manager overrides aren&apos;t supported, to keep flags consistent
          across teams.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        {FIELDS.map((field) => (
          <div key={field.key} className="space-y-1">
            <Label htmlFor={field.key}>{field.label}</Label>
            <Input
              id={field.key}
              type="number"
              min={1}
              value={form[field.key]}
              onChange={(e) => setForm({ ...form, [field.key]: Number(e.target.value) })}
            />
            <p className="text-xs text-muted-foreground">{field.help}</p>
          </div>
        ))}
      </CardContent>
      <CardFooter className="justify-end gap-2">
        {mutation.isSuccess && <p className="text-sm text-muted-foreground">Saved.</p>}
        <Button onClick={() => mutation.mutate(form)} disabled={mutation.isPending}>
          {mutation.isPending ? "Saving…" : "Save thresholds"}
        </Button>
      </CardFooter>
    </Card>
  );
}
