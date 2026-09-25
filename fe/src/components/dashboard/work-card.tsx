"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, ExternalLink, GitPullRequest, MessageSquare, MoreHorizontal, OctagonAlert, Clock, Link2, UserCheck } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { StatusBadge, type Tone } from "@/components/ui/status-badge";
import {
  CommentDialog,
  LinkMergeRequestDialog,
  MarkBlockedButton,
  RequestReviewDialog,
} from "@/components/dashboard/card-action-dialogs";
import { type WorkCard as WorkCardData } from "@/lib/dashboard-api";
import { unblockWorkItem } from "@/lib/dashboard-api";
import { updateItemPreferences } from "@/lib/my-dashboard-api";
import { invalidateSoon } from "@/lib/sync-api";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

const MR_BADGE: Record<string, { label: string; tone: Tone }> = {
  draft: { label: "Draft MR", tone: "neutral" },
  open: { label: "MR open", tone: "info" },
  approved: { label: "Approved", tone: "success" },
  pipeline_failing: { label: "Pipeline failing", tone: "danger" },
  merged: { label: "Merged", tone: "success" },
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

type DialogName = "comment" | "review" | "link" | "block" | null;

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
  const [dialog, setDialog] = useState<DialogName>(null);
  const isWorkItem = card.kind === "work_item";
  const opens = isWorkItem && onOpen;

  const preferences = useMutation({
    mutationFn: (patch: { watching?: boolean; snoozed_until?: string | null }) =>
      updateItemPreferences(card.id, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });
  const unblock = useMutation({
    mutationFn: () => unblockWorkItem(card.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      invalidateSoon(queryClient);
    },
  });

  const mr = card.mr_status ? MR_BADGE[card.mr_status] : null;
  const isBlocked = Boolean(card.blocked_reason);
  const isStale = card.is_flagged && !isBlocked && card.mr_status !== "pipeline_failing";
  const shownLabels = card.labels.slice(0, 2);
  const moreLabels = card.labels.length - shownLabels.length;

  function open() {
    if (opens) onOpen(card.id);
  }

  const dialogProps = (name: Exclude<DialogName, null>) => ({
    open: dialog === name,
    onOpenChange: (next: boolean) => setDialog(next ? name : null),
  });

  return (
    <div
      role={opens ? "button" : undefined}
      tabIndex={opens ? 0 : undefined}
      onClick={open}
      onKeyDown={(e) => {
        if (opens && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          open();
        }
      }}
      className={cn(
        "group rounded-xl border bg-card p-3 shadow-xs transition-shadow hover:shadow-md",
        opens && "cursor-pointer focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        isBlocked && "border-l-4 border-l-red-500",
        !isBlocked && card.mr_status === "pipeline_failing" && "border-l-4 border-l-red-400",
        isStale && "border-l-4 border-l-amber-400",
      )}
    >
      <div className="flex items-start gap-2">
        {opens ? (
          <p className="line-clamp-2 flex-1 text-sm font-medium leading-snug">{card.title}</p>
        ) : (
          <a
            href={card.web_url}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="line-clamp-2 flex-1 text-sm font-medium leading-snug hover:underline"
          >
            {card.title}
          </a>
        )}

        <DropdownMenu>
          <DropdownMenuTrigger
            onClick={(e) => e.stopPropagation()}
            aria-label="Actions"
            className="-mr-1 -mt-1 rounded-md p-1 text-muted-foreground opacity-60 outline-none hover:bg-muted hover:opacity-100 focus-visible:opacity-100 group-hover:opacity-100"
          >
            <MoreHorizontal className="size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-52" onClick={(e) => e.stopPropagation()}>
            <DropdownMenuItem onClick={() => setDialog("comment")}>
              <MessageSquare className="size-4" /> Comment
            </DropdownMenuItem>
            {card.linked_mr_id && (
              <DropdownMenuItem onClick={() => setDialog("review")}>
                <UserCheck className="size-4" /> Request review
              </DropdownMenuItem>
            )}
            {isWorkItem && (
              <DropdownMenuItem onClick={() => setDialog("link")}>
                <Link2 className="size-4" /> Link merge request
              </DropdownMenuItem>
            )}
            {isWorkItem &&
              (isBlocked ? (
                <DropdownMenuItem onClick={() => unblock.mutate()}>
                  <OctagonAlert className="size-4" /> Unblock
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem onClick={() => setDialog("block")}>
                  <OctagonAlert className="size-4" /> Mark blocked
                </DropdownMenuItem>
              ))}
            {isWorkItem && <DropdownMenuSeparator />}
            {isWorkItem && (
              <DropdownMenuItem onClick={() => preferences.mutate({ watching: !card.watching })}>
                {card.watching ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                {card.watching ? "Stop watching" : "Watch"}
              </DropdownMenuItem>
            )}
            {isWorkItem &&
              (card.snoozed_until ? (
                <DropdownMenuItem onClick={() => preferences.mutate({ snoozed_until: null })}>
                  <Clock className="size-4" /> Unsnooze
                </DropdownMenuItem>
              ) : (
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    <Clock className="size-4" /> Snooze
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent className="min-w-44">
                    {SNOOZE_OPTIONS.map((option) => (
                      <DropdownMenuItem
                        key={option.days}
                        onClick={() => preferences.mutate({ snoozed_until: daysFromNow(option.days) })}
                      >
                        {option.label}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
              ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => window.open(card.web_url, "_blank", "noreferrer")}>
              <ExternalLink className="size-4" /> Open in GitLab
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <p className="mt-1 truncate text-xs text-muted-foreground">
        {card.project_name}
        {card.milestone_title && ` · ${card.milestone_title}`} · {timeAgo(card.last_activity_at)}
      </p>

      {(mr || isBlocked || isStale || shownLabels.length > 0 || card.watching) && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {isBlocked && <StatusBadge tone="danger">Blocked</StatusBadge>}
          {mr &&
            (card.mr_status === "pipeline_failing" && card.pipeline_url ? (
              <a
                href={card.pipeline_url}
                target="_blank"
                rel="noreferrer"
                title="See the failed pipeline"
                onClick={(e) => e.stopPropagation()}
              >
                <StatusBadge tone={mr.tone}>
                  <GitPullRequest className="size-3" /> {mr.label} ↗
                </StatusBadge>
              </a>
            ) : (
              <StatusBadge tone={mr.tone}>
                <GitPullRequest className="size-3" /> {mr.label}
              </StatusBadge>
            ))}
          {isStale && <StatusBadge tone="warning">Stale</StatusBadge>}
          {shownLabels.map((label) => (
            <StatusBadge key={label}>{label}</StatusBadge>
          ))}
          {moreLabels > 0 && <span className="text-[11px] text-muted-foreground">+{moreLabels}</span>}
          {card.watching && <Eye className="size-3.5 text-muted-foreground" aria-label="Watching" />}
        </div>
      )}

      {card.blocked_reason && <p className="mt-2 line-clamp-2 text-xs text-red-700 dark:text-red-300">{card.blocked_reason}</p>}
      {card.snoozed_until && (
        <p className="mt-2 text-xs text-muted-foreground">
          Snoozed until {new Date(card.snoozed_until).toLocaleDateString()}
        </p>
      )}

      <div onClick={(e) => e.stopPropagation()}>
        <CommentDialog kind={card.kind} targetId={card.id} title={card.title} queryKeys={queryKeys} {...dialogProps("comment")} />
        {card.linked_mr_id && (
          <RequestReviewDialog mergeRequestId={card.linked_mr_id} title={card.title} queryKeys={queryKeys} {...dialogProps("review")} />
        )}
        {isWorkItem && (
          <LinkMergeRequestDialog workItemId={card.id} title={card.title} queryKeys={queryKeys} {...dialogProps("link")} />
        )}
        {isWorkItem && !isBlocked && (
          <MarkBlockedButton
            workItemId={card.id}
            title={card.title}
            blockedReason={card.blocked_reason}
            queryKeys={queryKeys}
            {...dialogProps("block")}
          />
        )}
      </div>
    </div>
  );
}
