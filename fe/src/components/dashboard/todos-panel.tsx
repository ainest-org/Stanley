"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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

export function TodosPanel({ onOpenItem }: { onOpenItem: (workItemId: string) => void }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["todos"], queryFn: fetchTodos });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["todos"] });

  const done = useMutation({ mutationFn: markTodoDone, onSuccess: refresh });
  const doneAll = useMutation({ mutationFn: markAllTodosDone, onSuccess: refresh });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>GitLab inbox</span>
          {(data?.todos.length ?? 0) > 0 && (
            <Button size="xs" variant="ghost" disabled={doneAll.isPending} onClick={() => doneAll.mutate()}>
              Mark all done
            </Button>
          )}
        </CardTitle>
        <CardDescription>Your GitLab To-Dos: mentions, replies and review requests.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {data?.live_error && <p className="text-sm text-amber-700 dark:text-amber-400">{data.live_error}</p>}
        {data && !data.live_error && data.todos.length === 0 && (
          <p className="text-sm text-muted-foreground">Inbox zero. Nothing needs you.</p>
        )}
        {(done.isError || doneAll.isError) && (
          <p className="text-sm text-destructive">{errorMessage(done.error ?? doneAll.error)}</p>
        )}
        {data?.todos.map((todo) => (
          <div key={todo.id} className="space-y-1 rounded-md border p-2 text-sm">
            <div className="flex items-center gap-2">
              <Badge variant="outline">{ACTION_LABEL[todo.action] ?? todo.action}</Badge>
              <span className="text-xs text-muted-foreground">
                {todo.author ? `${todo.author} · ` : ""}
                {timeAgo(todo.created_at)}
              </span>
            </div>
            {todo.work_item_id ? (
              <button
                type="button"
                className="text-left font-medium hover:underline"
                onClick={() => onOpenItem(todo.work_item_id as string)}
              >
                {todo.title}
              </button>
            ) : (
              <a href={todo.url ?? "#"} target="_blank" rel="noreferrer" className="font-medium hover:underline">
                {todo.title}
              </a>
            )}
            {todo.body && todo.body !== todo.title && (
              <p className="line-clamp-2 text-xs text-muted-foreground">{todo.body}</p>
            )}
            <div className="flex items-center gap-2">
              {todo.project && <span className="text-xs text-muted-foreground">{todo.project}</span>}
              <Button size="xs" variant="ghost" disabled={done.isPending} onClick={() => done.mutate(todo.id)}>
                Done
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
