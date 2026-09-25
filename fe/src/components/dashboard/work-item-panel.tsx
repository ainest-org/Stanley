"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, GitPullRequest, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Pick } from "@/components/ui/pick";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { StatusBadge, type Tone } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { LinkMergeRequestDialog, MarkBlockedButton } from "@/components/dashboard/card-action-dialogs";
import { commentOn, errorMessage, setWorkItemMilestone, unlinkMergeRequest } from "@/lib/actions-api";
import { fetchWorkItemDetail, reassignWorkItem } from "@/lib/dashboard-api";
import { timeAgo } from "@/lib/format";
import { invalidateSoon } from "@/lib/sync-api";

const MR_BADGE: Record<string, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  open: { label: "Open", tone: "info" },
  approved: { label: "Approved", tone: "success" },
  pipeline_failing: { label: "Pipeline failing", tone: "danger" },
  merged: { label: "Merged", tone: "success" },
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

export function WorkItemPanel({
  itemId,
  onClose,
  members,
}: {
  itemId: string | null;
  onClose: () => void;
  members: { id: string; name: string }[];
}) {
  const queryClient = useQueryClient();
  const [reply, setReply] = useState("");
  const detailKey = ["work-item-detail", itemId];
  const { data, isLoading, isError, error } = useQuery({
    queryKey: detailKey,
    queryFn: () => fetchWorkItemDetail(itemId as string),
    enabled: itemId !== null,
  });

  const queryKeys = [detailKey, ["team-board"], ["my-work"]];
  const refresh = () => {
    for (const queryKey of queryKeys) queryClient.invalidateQueries({ queryKey });
    invalidateSoon(queryClient);
  };

  const reassign = useMutation({
    mutationFn: (assigneeId: string) => reassignWorkItem(itemId as string, assigneeId),
    onSuccess: refresh,
  });
  const changeMilestone = useMutation({
    mutationFn: (milestoneId: string | null) => setWorkItemMilestone(itemId as string, milestoneId),
    onSuccess: refresh,
  });
  const unlink = useMutation({
    mutationFn: (mergeRequestId: string) => unlinkMergeRequest(itemId as string, mergeRequestId),
    onSuccess: refresh,
  });
  const post = useMutation({
    mutationFn: () => commentOn("work_item", itemId as string, reply.trim()),
    onSuccess: () => {
      setReply("");
      refresh();
    },
  });

  return (
    <Sheet open={itemId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-xl">
        <SheetHeader className="border-b p-5 pr-12">
          <SheetTitle className="text-lg leading-snug">{data?.title ?? "Work item"}</SheetTitle>
          <SheetDescription className="flex items-center gap-3">
            <span>{data?.project_name ?? "Loading…"}</span>
            {data && (
              <a
                href={data.web_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                Edit in GitLab <ExternalLink className="size-3" />
              </a>
            )}
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {isError && <p className="text-sm text-destructive">{errorMessage(error)}</p>}

          {data && (
            <>
              {data.live_error && (
                <p className="rounded-lg border border-amber-300/60 bg-amber-50 p-2.5 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                  {data.live_error}
                </p>
              )}

              <div className="flex flex-wrap items-center gap-1.5">
                <StatusBadge tone={data.state === "opened" ? "success" : "neutral"}>{data.state}</StatusBadge>
                <StatusBadge>{data.item_type}</StatusBadge>
                {data.due_date && <StatusBadge tone="info">due {data.due_date}</StatusBadge>}
                {data.labels.map((label) => (
                  <StatusBadge key={label} className="bg-transparent ring-1 ring-border">
                    {label}
                  </StatusBadge>
                ))}
              </div>

              {data.blocked_reason && (
                <div className="rounded-lg border border-red-300/60 bg-red-50 p-3 text-sm text-red-900 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
                  <span className="font-medium">Blocked:</span> {data.blocked_reason}
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-2">
                <Section title="Assignee">
                  <Pick
                    value={data.assignee?.id ?? null}
                    onChange={(id) => reassign.mutate(id)}
                    options={members.map((m) => ({ value: m.id, label: m.name }))}
                    placeholder="Unassigned"
                    disabled={reassign.isPending}
                  />
                  {reassign.isError && <p className="text-xs text-destructive">{errorMessage(reassign.error)}</p>}
                </Section>

                <Section title="Milestone">
                  {data.can_set_milestone ? (
                    <>
                      <Pick
                        value={data.milestone_id ?? "none"}
                        onChange={(id) => changeMilestone.mutate(id === "none" ? null : id)}
                        options={[
                          { value: "none", label: "No milestone" },
                          ...data.available_milestones.map((m) => ({ value: m.id, label: m.title })),
                        ]}
                        placeholder="No milestone"
                        disabled={changeMilestone.isPending}
                      />
                      {changeMilestone.isError && (
                        <p className="text-xs text-destructive">{errorMessage(changeMilestone.error)}</p>
                      )}
                    </>
                  ) : (
                    <p className="text-sm">
                      {data.milestone_title ?? "None"}
                      <span className="mt-1 block text-xs text-muted-foreground">
                        Only project Maintainers and Owners can change this.
                      </span>
                    </p>
                  )}
                </Section>
              </div>

              <div className="flex flex-wrap gap-2">
                <LinkMergeRequestDialog workItemId={data.id} title={data.title} queryKeys={queryKeys} />
                <MarkBlockedButton
                  workItemId={data.id}
                  title={data.title}
                  blockedReason={data.blocked_reason}
                  queryKeys={queryKeys}
                />
              </div>

              <Section title="Description">
                {data.description ? (
                  <div className="max-h-56 overflow-y-auto whitespace-pre-wrap rounded-lg bg-muted/60 p-3 text-sm">
                    {data.description}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No description.</p>
                )}
              </Section>

              <Section title={`Merge requests (${data.merge_requests.length})`}>
                {data.merge_requests.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    None linked yet. Use Link MR to connect one.
                  </p>
                )}
                {unlink.data?.note && <p className="text-xs text-amber-700 dark:text-amber-400">{unlink.data.note}</p>}
                {unlink.isError && <p className="text-xs text-destructive">{errorMessage(unlink.error)}</p>}
                <ul className="space-y-1.5">
                  {data.merge_requests.map((mr) => {
                    const badge = mr.status ? MR_BADGE[mr.status] : null;
                    return (
                      <li key={mr.id} className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm">
                        <GitPullRequest className="size-4 shrink-0 text-muted-foreground" />
                        <a href={mr.web_url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate hover:underline">
                          {mr.title}
                        </a>
                        {badge && <StatusBadge tone={badge.tone}>{badge.label}</StatusBadge>}
                        <Button size="xs" variant="ghost" disabled={unlink.isPending} onClick={() => unlink.mutate(mr.id)}>
                          Unlink
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              </Section>

              <Section title={`Comments (${data.comments.length})`}>
                {data.comments.length === 0 && <p className="text-sm text-muted-foreground">No comments yet.</p>}
                <ul className="space-y-3">
                  {data.comments.map((comment) => (
                    <li key={comment.id} className="flex gap-3">
                      <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
                        {comment.author.slice(0, 1)}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs text-muted-foreground">
                          <span className="font-medium text-foreground">{comment.author}</span> · {timeAgo(comment.created_at)}
                          {comment.via_stanley && <span className="italic"> · sent from Stanley</span>}
                        </p>
                        <p className="mt-0.5 whitespace-pre-wrap text-sm">{comment.body}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </Section>
            </>
          )}
        </div>

        {data && (
          <div className="space-y-2 border-t bg-card p-4">
            <Textarea
              rows={2}
              placeholder="Write a comment. It's posted to GitLab as you."
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && reply.trim() && !post.isPending) post.mutate();
              }}
            />
            {post.isError && <p className="text-xs text-destructive">{errorMessage(post.error)}</p>}
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Ctrl+Enter to send</span>
              <Button size="sm" disabled={!reply.trim() || post.isPending} onClick={() => post.mutate()}>
                <Send className="size-3.5" /> {post.isPending ? "Sending…" : "Comment"}
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
