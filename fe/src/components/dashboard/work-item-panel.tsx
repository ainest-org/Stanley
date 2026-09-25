"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Pick } from "@/components/ui/pick";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import {
  CommentDialog,
  LinkMergeRequestDialog,
  MarkBlockedButton,
} from "@/components/dashboard/card-action-dialogs";
import { Button } from "@/components/ui/button";
import { errorMessage, setWorkItemMilestone, unlinkMergeRequest } from "@/lib/actions-api";
import { fetchWorkItemDetail, reassignWorkItem } from "@/lib/dashboard-api";
import { MR_STATUS_LABEL, timeAgo } from "@/lib/format";

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
  const detailKey = ["work-item-detail", itemId];
  const { data, isLoading, isError, error } = useQuery({
    queryKey: detailKey,
    queryFn: () => fetchWorkItemDetail(itemId as string),
    enabled: itemId !== null,
  });

  const queryKeys = [detailKey, ["team-board"], ["my-work"]];

  const reassign = useMutation({
    mutationFn: (assigneeId: string) => reassignWorkItem(itemId as string, assigneeId),
    onSuccess: () => {
      for (const queryKey of queryKeys) queryClient.invalidateQueries({ queryKey });
    },
  });

  const refresh = () => {
    for (const queryKey of queryKeys) queryClient.invalidateQueries({ queryKey });
  };

  const changeMilestone = useMutation({
    mutationFn: (milestoneId: string | null) => setWorkItemMilestone(itemId as string, milestoneId),
    onSuccess: refresh,
  });

  const unlink = useMutation({
    mutationFn: (mergeRequestId: string) => unlinkMergeRequest(itemId as string, mergeRequestId),
    onSuccess: refresh,
  });

  return (
    <Sheet open={itemId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{data?.title ?? "Work item"}</SheetTitle>
          <SheetDescription>
            A read-only view of the GitLab item.{" "}
            {data && (
              <a href={data.web_url} target="_blank" rel="noreferrer" className="underline">
                Edit in GitLab
              </a>
            )}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-4 px-4 pb-6">
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {isError && <p className="text-sm text-destructive">{errorMessage(error)}</p>}

          {data && (
            <>
              {data.live_error && (
                <p className="rounded-md border border-amber-400/50 bg-amber-400/10 p-2 text-xs text-amber-700 dark:text-amber-400">
                  {data.live_error}
                </p>
              )}

              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <Badge variant="outline">{data.project_name}</Badge>
                <Badge variant="secondary">{data.state}</Badge>
                <Badge variant="secondary">{data.item_type}</Badge>
                {data.milestone_title && <Badge variant="outline">{data.milestone_title}</Badge>}
                {data.due_date && <Badge variant="outline">due {data.due_date}</Badge>}
                {data.labels.map((label) => (
                  <Badge key={label} variant="outline">
                    {label}
                  </Badge>
                ))}
              </div>

              {data.blocked_reason && (
                <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
                  Blocked: {data.blocked_reason}
                </p>
              )}

              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Assignee</p>
                <Pick
                  value={data.assignee?.id ?? null}
                  onChange={(id) => reassign.mutate(id)}
                  options={members.map((m) => ({ value: m.id, label: m.name }))}
                  placeholder="Unassigned"
                  disabled={reassign.isPending}
                />
                {reassign.isError && <p className="text-xs text-destructive">{errorMessage(reassign.error)}</p>}
              </div>

              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Milestone</p>
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
                    {data.milestone_title ?? "None"}{" "}
                    <span className="text-xs text-muted-foreground">
                      (only project Maintainers and Owners can change this)
                    </span>
                  </p>
                )}
              </div>

              <div className="flex flex-wrap gap-1.5">
                <CommentDialog kind="work_item" targetId={data.id} title={data.title} queryKeys={queryKeys} />
                <LinkMergeRequestDialog workItemId={data.id} title={data.title} queryKeys={queryKeys} />
                <MarkBlockedButton
                  workItemId={data.id}
                  title={data.title}
                  blockedReason={data.blocked_reason}
                  queryKeys={queryKeys}
                />
              </div>

              <Separator />

              <section className="space-y-1">
                <h3 className="text-sm font-medium">Description</h3>
                {data.description ? (
                  <p className="whitespace-pre-wrap text-sm">{data.description}</p>
                ) : (
                  <p className="text-sm text-muted-foreground">No description.</p>
                )}
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-medium">Merge requests</h3>
                {data.merge_requests.length === 0 && (
                  <p className="text-sm text-muted-foreground">No linked merge requests.</p>
                )}
                {unlink.data?.note && <p className="text-xs text-amber-700 dark:text-amber-400">{unlink.data.note}</p>}
                {unlink.isError && <p className="text-xs text-destructive">{errorMessage(unlink.error)}</p>}
                {data.merge_requests.map((mr) => (
                  <div key={mr.id} className="flex flex-wrap items-center gap-2 text-sm">
                    <a href={mr.web_url} target="_blank" rel="noreferrer" className="hover:underline">
                      {mr.title}
                    </a>
                    {mr.status && <Badge variant={mr.status === "pipeline_failing" ? "destructive" : "outline"}>{MR_STATUS_LABEL[mr.status] ?? mr.status}</Badge>}
                    {mr.pipeline_status && (
                      <span className="text-xs text-muted-foreground">pipeline {mr.pipeline_status}</span>
                    )}
                    <Button size="xs" variant="ghost" disabled={unlink.isPending} onClick={() => unlink.mutate(mr.id)}>
                      Unlink
                    </Button>
                  </div>
                ))}
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-medium">Comments</h3>
                {data.comments.length === 0 && <p className="text-sm text-muted-foreground">No comments.</p>}
                {data.comments.map((comment) => (
                  <div key={comment.id} className="rounded-md border p-2 text-sm">
                    <p className="mb-1 text-xs text-muted-foreground">
                      {comment.author} · {timeAgo(comment.created_at)}
                      {comment.via_stanley && <span className="ml-1 italic">· sent from Stanley</span>}
                    </p>
                    <p className="whitespace-pre-wrap">{comment.body}</p>
                  </div>
                ))}
              </section>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
