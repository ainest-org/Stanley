"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { StatusBadge } from "@/components/ui/status-badge";
import { errorMessage } from "@/lib/actions-api";
import { fetchTodos, markAllTodosDone, markTodoDone } from "@/lib/my-dashboard-api";
import { timeAgo } from "@/lib/format";

const ACTION_LABEL: Record<string, string> = {
  assigned: "Assigned to you",
  mentioned: "Mentioned you",
  directly_addressed: "Replied to you",
  review_requested: "Review requested",
  approval_required: "Approval needed",
  build_failed: "Pipeline failed",
  unmergeable: "Can't merge",
  merge_train_removed: "Removed from train",
  marked: "Marked",
};

/** The number shown on the Inbox button. Shares the query with the panel, so it costs nothing extra. */
export function useTodoCount() {
  const { data } = useQuery({ queryKey: ["todos"], queryFn: fetchTodos });
  return data?.todos.length ?? 0;
}

export function TodosSheet({
  open,
  onOpenChange,
  onOpenItem,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onOpenItem: (workItemId: string) => void;
}) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["todos"], queryFn: fetchTodos });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["todos"] });
  const done = useMutation({ mutationFn: markTodoDone, onSuccess: refresh });
  const doneAll = useMutation({ mutationFn: markAllTodosDone, onSuccess: refresh });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Inbox className="size-4" /> GitLab inbox
          </SheetTitle>
          <SheetDescription>Your GitLab To-Dos: mentions, replies and review requests.</SheetDescription>
        </SheetHeader>

        <div className="space-y-3 px-4 pb-6">
          {(data?.todos.length ?? 0) > 0 && (
            <Button size="sm" variant="outline" disabled={doneAll.isPending} onClick={() => doneAll.mutate()}>
              Mark all done
            </Button>
          )}
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {data?.live_error && <p className="text-sm text-amber-700 dark:text-amber-400">{data.live_error}</p>}
          {data && !data.live_error && data.todos.length === 0 && (
            <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
              Inbox zero. Nothing needs you.
            </p>
          )}
          {(done.isError || doneAll.isError) && (
            <p className="text-sm text-destructive">{errorMessage(done.error ?? doneAll.error)}</p>
          )}

          {data?.todos.map((todo) => (
            <div key={todo.id} className="space-y-1.5 rounded-lg border bg-card p-3 text-sm">
              <div className="flex items-center gap-2">
                <StatusBadge tone="info">{ACTION_LABEL[todo.action] ?? todo.action}</StatusBadge>
                <span className="text-xs text-muted-foreground">
                  {todo.author ? `${todo.author} · ` : ""}
                  {timeAgo(todo.created_at)}
                </span>
              </div>
              {todo.work_item_id ? (
                <button
                  type="button"
                  className="text-left font-medium hover:underline"
                  onClick={() => {
                    onOpenChange(false);
                    onOpenItem(todo.work_item_id as string);
                  }}
                >
                  {todo.title}
                </button>
              ) : (
                <a href={todo.url ?? "#"} target="_blank" rel="noreferrer" className="block font-medium hover:underline">
                  {todo.title}
                </a>
              )}
              {todo.body && todo.body !== todo.title && (
                <p className="line-clamp-2 text-xs text-muted-foreground">{todo.body}</p>
              )}
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{todo.project}</span>
                <Button size="xs" variant="ghost" disabled={done.isPending} onClick={() => done.mutate(todo.id)}>
                  Done
                </Button>
              </div>
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}
