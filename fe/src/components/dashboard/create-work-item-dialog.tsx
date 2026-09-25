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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Pick } from "@/components/ui/pick";
import {
  createWorkItem,
  errorMessage,
  fetchCreateOptions,
  fetchProjects,
  type CreateWorkItemInput,
} from "@/lib/actions-api";

const TYPE_OPTIONS = [
  { value: "issue", label: "Issue" },
  { value: "task", label: "Task" },
  { value: "incident", label: "Bug (incident)" },
];

const NONE = "none";

export function CreateWorkItemDialog({
  defaultAssigneeId,
  triggerLabel = "+ New work item",
  triggerVariant = "default",
  triggerSize = "default",
}: {
  defaultAssigneeId?: string;
  triggerLabel?: string;
  triggerVariant?: "default" | "outline" | "ghost";
  triggerSize?: "default" | "sm" | "xs";
}) {
  const [open, setOpen] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [itemType, setItemType] = useState<CreateWorkItemInput["item_type"]>("issue");
  const [assigneeId, setAssigneeId] = useState<string>(defaultAssigneeId ?? NONE);
  const [milestoneId, setMilestoneId] = useState<string>(NONE);
  const [labelIds, setLabelIds] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const queryClient = useQueryClient();

  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects, enabled: open });
  const options = useQuery({
    queryKey: ["create-options", projectId],
    queryFn: () => fetchCreateOptions(projectId as string),
    enabled: open && projectId !== null,
  });

  function reset() {
    setTitle("");
    setItemType("issue");
    setAssigneeId(defaultAssigneeId ?? NONE);
    setMilestoneId(NONE);
    setLabelIds([]);
    setDescription("");
    setDueDate("");
    setIdempotencyKey(crypto.randomUUID());
  }

  const mutation = useMutation({
    mutationFn: () =>
      createWorkItem({
        project_id: projectId as string,
        title: title.trim(),
        idempotency_key: idempotencyKey,
        item_type: itemType,
        description: description.trim() || undefined,
        assignee_user_id: assigneeId === NONE ? undefined : assigneeId,
        milestone_id: milestoneId === NONE ? undefined : milestoneId,
        label_ids: labelIds,
        due_date: dueDate || undefined,
      }),
    onSuccess: () => {
      setOpen(false);
      reset();
      for (const key of ["my-work", "team-board", "radar"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });

  function toggleLabel(id: string) {
    setLabelIds((current) => (current.includes(id) ? current.filter((l) => l !== id) : [...current, id]));
  }

  const canSubmit = projectId !== null && title.trim().length > 0 && !mutation.isPending;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant={triggerVariant} size={triggerSize} />}>{triggerLabel}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New work item</DialogTitle>
          <DialogDescription>
            Created in GitLab as you. It appears here straight away and stays in sync with GitLab.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Project</Label>
            <Pick
              value={projectId}
              onChange={(id) => {
                setProjectId(id);
                setAssigneeId(defaultAssigneeId ?? NONE);
                setMilestoneId(NONE);
                setLabelIds([]);
              }}
              options={(projects.data ?? []).map((p) => ({ value: p.id, label: p.name }))}
              placeholder="Choose a synced project"
            />
            {projects.data?.length === 0 && (
              <p className="text-xs text-muted-foreground">No synced projects. Sync one in Settings first.</p>
            )}
          </div>

          <div className="space-y-1">
            <Label htmlFor="wi-title">Title</Label>
            <Input id="wi-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Type</Label>
              <Pick
                value={itemType}
                onChange={(v) => setItemType(v as CreateWorkItemInput["item_type"])}
                options={TYPE_OPTIONS}
                placeholder="Type"
              />
            </div>
            <div className="space-y-1">
              <Label>Assignee</Label>
              <Pick
                value={assigneeId}
                onChange={setAssigneeId}
                disabled={!projectId}
                options={[
                  { value: NONE, label: "Unassigned" },
                  ...(options.data?.members ?? []).map((m) => ({ value: m.id, label: m.name })),
                ]}
                placeholder="Unassigned"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Milestone</Label>
              <Pick
                value={milestoneId}
                onChange={setMilestoneId}
                disabled={!projectId}
                options={[
                  { value: NONE, label: "None" },
                  ...(options.data?.milestones ?? []).map((m) => ({ value: m.id, label: m.title })),
                ]}
                placeholder="None"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="wi-due">Due date</Label>
              <Input id="wi-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </div>
          </div>

          {(options.data?.labels.length ?? 0) > 0 && (
            <div className="space-y-1">
              <Label>Labels</Label>
              <div className="flex flex-wrap gap-1.5">
                {options.data?.labels.map((label) => (
                  <button key={label.id} type="button" onClick={() => toggleLabel(label.id)}>
                    <Badge variant={labelIds.includes(label.id) ? "default" : "outline"}>{label.name}</Badge>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-1">
            <Label htmlFor="wi-desc">Description</Label>
            <Textarea
              id="wi-desc"
              placeholder="Markdown supported"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {mutation.isError && (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
              {errorMessage(mutation.error)}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button disabled={!canSubmit} onClick={() => mutation.mutate()}>
            {mutation.isPending ? "Creating…" : "Create work item"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
