"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fetchTeamBoard, reassignWorkItem, type Swimlane } from "@/lib/dashboard-api";

export default function TeamBoardPage() {
  const queryKey = ["team-board"];
  const { data, isLoading } = useQuery({ queryKey, queryFn: fetchTeamBoard });
  const queryClient = useQueryClient();

  const reassignMutation = useMutation({
    mutationFn: ({ itemId, assigneeId }: { itemId: string; assigneeId: string }) =>
      reassignWorkItem(itemId, assigneeId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold mb-1">Team Board</h1>
        <p className="text-sm text-muted-foreground">
          One lane per person, not a status board — see PRD Section 7 for why.
        </p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {data && (
        <div className="space-y-6">
          <AttentionStrip board={data} />

          <div className="space-y-3">
            {data.swimlanes.map((lane) => (
              <SwimlaneRow
                key={lane.user_id}
                lane={lane}
                allMembers={data.swimlanes.map((l) => ({ id: l.user_id, name: l.name }))}
                onReassign={(itemId, assigneeId) => reassignMutation.mutate({ itemId, assigneeId })}
                pending={reassignMutation.isPending}
              />
            ))}
          </div>
        </div>
      )}
    </AppShell>
  );
}

function AttentionStrip({ board }: { board: Awaited<ReturnType<typeof fetchTeamBoard>> }) {
  const { attention } = board;
  const hasAny =
    attention.stalled_mrs.length > 0 ||
    attention.unassigned_items.length > 0 ||
    attention.reviews_pending_sla.length > 0 ||
    attention.idle_engineers.length > 0 ||
    attention.overloaded_engineers.length > 0;

  if (!hasAny) return null;

  return (
    <Card className="border-amber-400/50">
      <CardHeader>
        <CardTitle className="text-base">Needs your attention</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2 text-sm">
        {attention.stalled_mrs.map((mr) => (
          <a key={mr.id} href={mr.web_url} target="_blank" rel="noreferrer">
            <Badge variant="outline">Stalled MR: {mr.title}</Badge>
          </a>
        ))}
        {attention.unassigned_items.map((item) => (
          <a key={item.id} href={item.web_url} target="_blank" rel="noreferrer">
            <Badge variant="outline">Unassigned: {item.title}</Badge>
          </a>
        ))}
        {attention.reviews_pending_sla.map((mr) => (
          <a key={mr.id} href={mr.web_url} target="_blank" rel="noreferrer">
            <Badge variant="destructive">Review overdue: {mr.title}</Badge>
          </a>
        ))}
        {attention.idle_engineers.map((person) => (
          <Badge key={person.user_id} variant="secondary">
            Idle: {person.name}
          </Badge>
        ))}
        {attention.overloaded_engineers.map((person) => (
          <Badge key={person.user_id} variant="secondary">
            Overloaded: {person.name} ({person.active_count})
          </Badge>
        ))}
      </CardContent>
    </Card>
  );
}

function SwimlaneRow({
  lane,
  allMembers,
  onReassign,
  pending,
}: {
  lane: Swimlane;
  allMembers: { id: string; name: string }[];
  onReassign: (itemId: string, assigneeId: string) => void;
  pending: boolean;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start">
        <div className="flex w-48 shrink-0 items-center gap-2">
          <Avatar className="h-7 w-7">
            <AvatarImage src={lane.avatar_url ?? undefined} alt={lane.name} />
            <AvatarFallback>{lane.name.slice(0, 1)}</AvatarFallback>
          </Avatar>
          <div>
            <p className="text-sm font-medium leading-none">{lane.name}</p>
            <div className="mt-1 flex gap-1">
              {lane.blocked_count > 0 && (
                <Badge variant="destructive" className="text-xs">
                  {lane.blocked_count} blocked
                </Badge>
              )}
              {lane.stale_count > 0 && (
                <Badge variant="secondary" className="text-xs">
                  {lane.stale_count} stale
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-1 flex-wrap gap-2">
          {lane.items.length === 0 && <p className="text-xs text-muted-foreground">No active items.</p>}
          {lane.items.map((item) => (
            <div
              key={item.id}
              className={`flex items-center gap-2 rounded-md border px-2 py-1.5 text-xs ${
                item.is_blocked ? "border-destructive/40" : item.is_stale ? "border-amber-400/50" : ""
              }`}
            >
              <a href={item.web_url} target="_blank" rel="noreferrer" className="hover:underline">
                {item.title}
              </a>
              <span className="text-muted-foreground">· {item.project_name}</span>
              <Select disabled={pending} onValueChange={(assigneeId) => onReassign(item.id, assigneeId as string)}>
                <SelectTrigger size="sm" className="h-6 w-28 text-xs">
                  <SelectValue placeholder="Reassign…" />
                </SelectTrigger>
                <SelectContent>
                  {allMembers.map((member) => (
                    <SelectItem key={member.id} value={member.id}>
                      {member.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
