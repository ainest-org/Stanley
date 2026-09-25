"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { markWorkItemBlocked, unblockWorkItem, type WorkCard as WorkCardData } from "@/lib/dashboard-api";
import { timeAgo, MR_STATUS_LABEL } from "@/lib/format";

const MR_BADGE_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "secondary",
  open: "outline",
  approved: "default",
  pipeline_failing: "destructive",
  merged: "default",
};

export function WorkCard({ card, queryKey }: { card: WorkCardData; queryKey: unknown[] }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [reason, setReason] = useState("");
  const queryClient = useQueryClient();

  const blockMutation = useMutation({
    mutationFn: () => markWorkItemBlocked(card.id, reason),
    onSuccess: () => {
      setDialogOpen(false);
      setReason("");
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const unblockMutation = useMutation({
    mutationFn: () => unblockWorkItem(card.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  return (
    <Card className={card.is_flagged ? "border-destructive/40" : undefined}>
      <CardContent className="space-y-2 py-1">
        <a href={card.web_url} target="_blank" rel="noreferrer" className="text-sm font-medium hover:underline">
          {card.title}
        </a>
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <span>{card.project_name}</span>
          <span>·</span>
          <span>{timeAgo(card.last_activity_at)}</span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {card.mr_status && (
            <Badge variant={MR_BADGE_VARIANT[card.mr_status] ?? "outline"} className="text-xs">
              {MR_STATUS_LABEL[card.mr_status] ?? card.mr_status}
            </Badge>
          )}
          {card.is_flagged && (
            <Badge variant="destructive" className="text-xs">
              Blocked
            </Badge>
          )}
        </div>
        {card.blocked_reason && <p className="text-xs text-destructive">{card.blocked_reason}</p>}

        {card.kind === "work_item" && (
          <div className="pt-1">
            {card.blocked_reason ? (
              <Button size="sm" variant="outline" disabled={unblockMutation.isPending} onClick={() => unblockMutation.mutate()}>
                Unblock
              </Button>
            ) : (
              <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogTrigger render={<Button size="sm" variant="outline" />}>Mark blocked</DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Mark &quot;{card.title}&quot; as blocked</DialogTitle>
                    <DialogDescription>
                      Visible to your manager and surfaced on Team Board / Radar. This is the
                      only thing this tool stores outside GitLab for a work item.
                    </DialogDescription>
                  </DialogHeader>
                  <Textarea
                    placeholder="What's it blocked on?"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                  <DialogFooter>
                    <Button disabled={!reason.trim() || blockMutation.isPending} onClick={() => blockMutation.mutate()}>
                      Mark blocked
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
