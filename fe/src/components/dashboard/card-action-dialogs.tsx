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
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Pick } from "@/components/ui/pick";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  commentOn,
  errorMessage,
  fetchAllMembers,
  fetchLinkableMergeRequests,
  linkMergeRequest,
  requestReview,
} from "@/lib/actions-api";
import { invalidateSoon } from "@/lib/sync-api";
import { markWorkItemBlocked, unblockWorkItem } from "@/lib/dashboard-api";

function ErrorBox({ error }: { error: unknown }) {
  return (
    <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
      {errorMessage(error)}
    </p>
  );
}

/** Dialogs can be opened by their own button, or controlled from outside (e.g. a card's menu). */
function useDialogState(open: boolean | undefined, onOpenChange: ((open: boolean) => void) | undefined) {
  const [internal, setInternal] = useState(false);
  const controlled = open !== undefined && onOpenChange !== undefined;
  return [controlled ? open : internal, controlled ? onOpenChange : setInternal, controlled] as const;
}

export function CommentDialog({
  open: openProp,
  onOpenChange,
  kind,
  targetId,
  title,
  queryKeys,
}: {
  kind: "work_item" | "merge_request";
  targetId: string;
  title: string;
  queryKeys: unknown[][];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen, controlled] = useDialogState(openProp, onOpenChange);
  const [body, setBody] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => commentOn(kind, targetId, body.trim()),
    onSuccess: () => {
      setOpen(false);
      setBody("");
      for (const queryKey of queryKeys) queryClient.invalidateQueries({ queryKey });
      invalidateSoon(queryClient);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {!controlled && <DialogTrigger render={<Button size="sm" variant="outline" />}>Comment</DialogTrigger>}
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Comment on &quot;{title}&quot;</DialogTitle>
          <DialogDescription>Posted to the real GitLab thread, as you.</DialogDescription>
        </DialogHeader>
        <Textarea placeholder="Write a comment…" value={body} onChange={(e) => setBody(e.target.value)} />
        {mutation.isError && <ErrorBox error={mutation.error} />}
        <DialogFooter>
          <Button disabled={!body.trim() || mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending ? "Posting…" : "Post comment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function RequestReviewDialog({
  open: openProp,
  onOpenChange,
  mergeRequestId,
  title,
  queryKeys,
}: {
  mergeRequestId: string;
  title: string;
  queryKeys: unknown[][];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen, controlled] = useDialogState(openProp, onOpenChange);
  const [reviewerId, setReviewerId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const members = useQuery({ queryKey: ["members"], queryFn: fetchAllMembers, enabled: open });

  const mutation = useMutation({
    mutationFn: () => requestReview(mergeRequestId, reviewerId as string),
    onSuccess: () => {
      setOpen(false);
      setReviewerId(null);
      for (const queryKey of queryKeys) queryClient.invalidateQueries({ queryKey });
      invalidateSoon(queryClient);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {!controlled && <DialogTrigger render={<Button size="sm" variant="outline" />}>Request review</DialogTrigger>}
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Request a review on &quot;{title}&quot;</DialogTitle>
          <DialogDescription>Adds them as a reviewer on the merge request in GitLab.</DialogDescription>
        </DialogHeader>
        <Pick
          value={reviewerId}
          onChange={setReviewerId}
          options={(members.data ?? []).map((m) => ({ value: m.id, label: m.name }))}
          placeholder="Choose a reviewer"
        />
        {mutation.isError && <ErrorBox error={mutation.error} />}
        <DialogFooter>
          <Button disabled={!reviewerId || mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending ? "Requesting…" : "Request review"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function MarkBlockedButton({
  open: openProp,
  onOpenChange,
  workItemId,
  title,
  blockedReason,
  queryKeys,
}: {
  workItemId: string;
  title: string;
  blockedReason: string | null;
  queryKeys: unknown[][];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen, controlled] = useDialogState(openProp, onOpenChange);
  const [reason, setReason] = useState("");
  const queryClient = useQueryClient();
  const refresh = () => {
    for (const queryKey of queryKeys) queryClient.invalidateQueries({ queryKey });
  };

  const block = useMutation({
    mutationFn: () => markWorkItemBlocked(workItemId, reason.trim()),
    onSuccess: () => {
      setOpen(false);
      setReason("");
      refresh();
    },
  });
  const unblock = useMutation({ mutationFn: () => unblockWorkItem(workItemId), onSuccess: refresh });

  if (blockedReason) {
    return (
      <Button size="sm" variant="outline" disabled={unblock.isPending} onClick={() => unblock.mutate()}>
        Unblock
      </Button>
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {!controlled && <DialogTrigger render={<Button size="sm" variant="outline" />}>Mark blocked</DialogTrigger>}
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Mark &quot;{title}&quot; as blocked</DialogTitle>
          <DialogDescription>
            Visible to your manager and surfaced on Team Board / Radar. This is the only thing
            Stanley stores outside GitLab for a work item.
          </DialogDescription>
        </DialogHeader>
        <Textarea placeholder="What's it blocked on?" value={reason} onChange={(e) => setReason(e.target.value)} />
        {block.isError && <ErrorBox error={block.error} />}
        <DialogFooter>
          <Button disabled={!reason.trim() || block.isPending} onClick={() => block.mutate()}>
            Mark blocked
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function LinkMergeRequestDialog({
  open: openProp,
  onOpenChange,
  workItemId,
  title,
  queryKeys,
}: {
  workItemId: string;
  title: string;
  queryKeys: unknown[][];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen, controlled] = useDialogState(openProp, onOpenChange);
  const [iid, setIid] = useState<string | null>(null);
  const [closes, setCloses] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const queryClient = useQueryClient();
  const candidates = useQuery({
    queryKey: ["linkable-mrs", workItemId, search],
    queryFn: () => fetchLinkableMergeRequests(workItemId, search),
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: () => linkMergeRequest(workItemId, iid as string, closes),
    onSuccess: (result) => {
      for (const queryKey of [...queryKeys, ["linkable-mrs", workItemId]]) queryClient.invalidateQueries({ queryKey });
      invalidateSoon(queryClient);
      if (result.note) return; // keep the dialog open so the note stays readable
      setOpen(false);
      setIid(null);
      setCloses(false);
    },
  });

  const list = candidates.data?.merge_requests ?? [];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {!controlled && <DialogTrigger render={<Button size="sm" variant="outline" />}>Link MR</DialogTrigger>}
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Link a merge request to &quot;{title}&quot;</DialogTitle>
          <DialogDescription>
            Adds a &quot;Related to&quot; reference to the merge request description in GitLab. An item can have several
            merge requests, and a merge request can serve several items.
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(searchInput.trim());
            setIid(null);
          }}
        >
          <Input
            placeholder="Search open merge requests by title…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          <Button type="submit" variant="outline">
            Search
          </Button>
        </form>

        {candidates.isLoading && <p className="text-sm text-muted-foreground">Loading merge requests from GitLab…</p>}
        {candidates.isError && <ErrorBox error={candidates.error} />}
        {candidates.data?.live_error && (
          <p className="text-sm text-amber-700 dark:text-amber-400">{candidates.data.live_error}</p>
        )}
        {candidates.data && list.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No open merge requests {search ? `matching "${search}" ` : ""}found in {candidates.data.project_name} that
            you can see, or they already reference this item.
          </p>
        )}
        {list.length > 0 && (
          <Pick
            value={iid}
            onChange={setIid}
            options={list.map((mr) => ({
              value: mr.iid,
              label: `!${mr.iid} ${mr.title}${mr.mine ? " (yours)" : mr.author ? ` (${mr.author})` : ""}`,
            }))}
            placeholder={`Choose from ${list.length} open merge request${list.length === 1 ? "" : "s"}`}
          />
        )}

        <div className="flex items-center gap-2">
          <Switch id={`closes-${workItemId}`} checked={closes} onCheckedChange={setCloses} />
          <Label htmlFor={`closes-${workItemId}`} className="text-sm">
            Close this item when the merge request merges
          </Label>
        </div>
        {mutation.isError && <ErrorBox error={mutation.error} />}
        {mutation.data?.note && <p className="text-sm text-amber-700 dark:text-amber-400">{mutation.data.note}</p>}
        <DialogFooter>
          <Button disabled={!iid || mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending ? "Linking..." : "Link merge request"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
