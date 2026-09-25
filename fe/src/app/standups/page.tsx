"use client";

import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { WorkItemPanel } from "@/components/dashboard/work-item-panel";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fetchAllMembers } from "@/lib/actions-api";
import { fetchStandups, setFollow } from "@/lib/standups-api";

function isoDay(date: Date): string {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function shiftDay(day: string, delta: number): string {
  const date = new Date(`${day}T12:00:00`);
  date.setDate(date.getDate() + delta);
  return isoDay(date);
}

function Lines({ text }: { text: string }) {
  if (!text.trim()) return <p className="text-sm text-muted-foreground">Nothing written.</p>;
  return <p className="whitespace-pre-wrap text-sm">{text}</p>;
}

export default function StandupsPage() {
  const today = isoDay(new Date());
  const [day, setDay] = useState(today);
  const [scope, setScope] = useState<"all" | "following">("all");
  const [openItemId, setOpenItemId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["standups", day, scope],
    queryFn: () => fetchStandups(day, scope),
    placeholderData: keepPreviousData,
  });
  const members = useQuery({ queryKey: ["members"], queryFn: fetchAllMembers }).data ?? [];

  const follow = useMutation({
    mutationFn: ({ id, following }: { id: string; following: boolean }) => setFollow(id, following),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["standups"] }),
  });

  return (
    <AppShell>
      <div className="mb-4 space-y-1">
        <h1 className="text-xl font-semibold">Standups</h1>
        <p className="text-sm text-muted-foreground">
          Everyone&apos;s optional daily check-ins in one place, instead of a meeting. Skipping is fine and is never
          flagged.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" onClick={() => setDay(shiftDay(day, -1))}>
          ←
        </Button>
        <Input type="date" className="w-40" value={day} max={today} onChange={(e) => e.target.value && setDay(e.target.value)} />
        <Button size="sm" variant="outline" disabled={day >= today} onClick={() => setDay(shiftDay(day, 1))}>
          →
        </Button>
        {day !== today && (
          <Button size="sm" variant="ghost" onClick={() => setDay(today)}>
            Today
          </Button>
        )}
        <div className="ml-auto flex gap-1">
          <Button size="sm" variant={scope === "all" ? "default" : "outline"} onClick={() => setScope("all")}>
            Everyone
          </Button>
          <Button
            size="sm"
            variant={scope === "following" ? "default" : "outline"}
            onClick={() => setScope("following")}
          >
            Following ({data?.following_count ?? 0})
          </Button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {data && (
        <div className="max-w-4xl space-y-6">
          <Card className={data.blockers.length > 0 ? "border-destructive/40" : undefined}>
            <CardHeader>
              <CardTitle className="text-base">Blockers ({data.blockers.length})</CardTitle>
              <CardDescription>From check-ins, plus items marked blocked in Stanley.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {data.blockers.length === 0 && <p className="text-muted-foreground">No blockers reported.</p>}
              {data.blockers.map((blocker, index) => (
                <div key={index} className="flex flex-wrap items-baseline gap-2">
                  <Badge variant={blocker.source === "flag" ? "destructive" : "outline"}>
                    {blocker.source === "flag" ? "Marked blocked" : "Check-in"}
                  </Badge>
                  {blocker.person && <span className="font-medium">{blocker.person}</span>}
                  {blocker.work_item_id && (
                    <button
                      type="button"
                      className="font-medium hover:underline"
                      onClick={() => setOpenItemId(blocker.work_item_id as string)}
                    >
                      {blocker.title}
                    </button>
                  )}
                  <span className="text-muted-foreground">{blocker.text}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          {data.submitted.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {scope === "following" && data.following_count === 0
                ? "You aren't following anyone yet. Switch to Everyone and follow people from their cards."
                : "No check-ins for this day."}
            </p>
          )}

          <div className="space-y-3">
            {data.submitted.map((person) => (
              <Card key={person.user_id}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Avatar className="h-6 w-6">
                      <AvatarImage src={person.avatar_url ?? undefined} alt={person.name} />
                      <AvatarFallback>{person.name.slice(0, 1)}</AvatarFallback>
                    </Avatar>
                    {person.name}
                    <span className="text-xs font-normal text-muted-foreground">
                      {new Date(person.submitted_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                    <Button
                      size="xs"
                      variant="ghost"
                      className="ml-auto"
                      disabled={follow.isPending}
                      onClick={() => follow.mutate({ id: person.user_id, following: !person.following })}
                    >
                      {person.following ? "Unfollow" : "Follow"}
                    </Button>
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-3">
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Did</p>
                    <Lines text={person.did} />
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Doing</p>
                    <Lines text={person.doing} />
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Blockers</p>
                    <Lines text={person.blockers} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {data.no_check_in.length > 0 && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
              <span>No check-in:</span>
              {data.no_check_in.map((person) => (
                <span key={person.user_id} className="flex items-center gap-1">
                  {person.name}
                  <Button
                    size="xs"
                    variant="ghost"
                    disabled={follow.isPending}
                    onClick={() => follow.mutate({ id: person.user_id, following: !person.following })}
                  >
                    {person.following ? "Unfollow" : "Follow"}
                  </Button>
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <WorkItemPanel itemId={openItemId} onClose={() => setOpenItemId(null)} members={members} />
    </AppShell>
  );
}
