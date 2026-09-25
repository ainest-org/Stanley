"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  CommentDialog,
  LinkMergeRequestDialog,
  MarkBlockedButton,
  RequestReviewDialog,
} from "@/components/dashboard/card-action-dialogs";
import { type WorkCard as WorkCardData } from "@/lib/dashboard-api";
import { updateItemPreferences } from "@/lib/my-dashboard-api";
import { timeAgo, MR_STATUS_LABEL } from "@/lib/format";

const MR_BADGE_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "secondary",
  open: "outline",
  approved: "default",
  pipeline_failing: "destructive",
  merged: "default",
};

const SNOOZE_OPTIONS = [
  { label: "Until tomorrow", days: 1 },
  { label: "For 3 days", days: 3 },
  { label: "Until next week", days: 7 },
];

function daysFromNow(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  date.setHours(8, 0, 0, 0);
  return date.toISOString();
}

export function WorkCard({
  card,
  queryKey,
  onOpen,
}: {
  card: WorkCardData;
  queryKey: unknown[];
  onOpen?: (workItemId: string) => void;
}) {
  const queryKeys = [queryKey];
  const queryClient = useQueryClient();

  const preferences = useMutation({
    mutationFn: (patch: { watching?: boolean; snoozed_until?: string | null }) =>
      updateItemPreferences(card.id, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const isWorkItem = card.kind === "work_item";

  return (
    <Card className={card.is_flagged ? "border-destructive/40" : undefined}>
      <CardContent className="space-y-2 py-1">
        {isWorkItem && onOpen ? (
          <div className="flex items-start justify-between gap-2">
            <button
              type="button"
              onClick={() => onOpen(card.id)}
              className="text-left text-sm font-medium hover:underline"
            >
              {card.title}
            </button>
            <a
              href={card.web_url}
              target="_blank"
              rel="noreferrer"
              title="Open in GitLab"
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              GitLab
            </a>
          </div>
        ) : (
          <a href={card.web_url} target="_blank" rel="noreferrer" className="text-sm font-medium hover:underline">
            {card.title}
          </a>
        )}

        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <span>{card.project_name}</span>
          {card.milestone_title && (
            <>
              <span>·</span>
              <span>{card.milestone_title}</span>
            </>
          )}
          <span>·</span>
          <span>{timeAgo(card.last_activity_at)}</span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {card.mr_status &&
            (card.pipeline_url && card.mr_status === "pipeline_failing" ? (
              <a href={card.pipeline_url} target="_blank" rel="noreferrer" title="See the failed pipeline">
                <Badge variant="destructive" className="text-xs">
                  {MR_STATUS_LABEL[card.mr_status]} ↗
                </Badge>
              </a>
            ) : (
              <Badge variant={MR_BADGE_VARIANT[card.mr_status] ?? "outline"} className="text-xs">
                {MR_STATUS_LABEL[card.mr_status] ?? card.mr_status}
              </Badge>
            ))}
          {card.is_flagged && (
            <Badge variant="destructive" className="text-xs">
              Blocked
            </Badge>
          )}
          {card.labels.slice(0, 3).map((label) => (
            <Badge key={label} variant="outline" className="text-xs">
              {label}
            </Badge>
          ))}
        </div>
        {card.blocked_reason && <p className="text-xs text-destructive">{card.blocked_reason}</p>}
        {card.snoozed_until && (
          <p className="text-xs text-muted-foreground">
            Snoozed until {new Date(card.snoozed_until).toLocaleDateString()}
          </p>
        )}

        <div className="flex flex-wrap gap-1.5 pt-1">
          <CommentDialog kind={card.kind} targetId={card.id} title={card.title} queryKeys={queryKeys} />
          {card.linked_mr_id && (
            <RequestReviewDialog mergeRequestId={card.linked_mr_id} title={card.title} queryKeys={queryKeys} />
          )}
          {isWorkItem && <LinkMergeRequestDialog workItemId={card.id} title={card.title} queryKeys={queryKeys} />}
          {isWorkItem && (
            <MarkBlockedButton
              workItemId={card.id}
              title={card.title}
              blockedReason={card.blocked_reason}
              queryKeys={queryKeys}
            />
          )}
          {isWorkItem && (
            <Button
              size="sm"
              variant="ghost"
              disabled={preferences.isPending}
              onClick={() => preferences.mutate({ watching: !card.watching })}
            >
              {card.watching ? "Unwatch" : "Watch"}
            </Button>
          )}
          {isWorkItem &&
            (card.snoozed_until ? (
              <Button
                size="sm"
                variant="ghost"
                disabled={preferences.isPending}
                onClick={() => preferences.mutate({ snoozed_until: null })}
              >
                Unsnooze
              </Button>
            ) : (
              <DropdownMenu>
                <DropdownMenuTrigger render={<Button size="sm" variant="ghost" />}>Snooze</DropdownMenuTrigger>
                <DropdownMenuContent>
                  {SNOOZE_OPTIONS.map((option) => (
                    <DropdownMenuItem
                      key={option.days}
                      onClick={() => preferences.mutate({ snoozed_until: daysFromNow(option.days) })}
                    >
                      {option.label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            ))}
        </div>
      </CardContent>
    </Card>
  );
}
