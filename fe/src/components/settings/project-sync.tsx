"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  fetchSyncedProjects,
  searchGitLabProjects,
  setSyncedProjectActive,
  syncProject,
  type SyncedProject,
} from "@/lib/admin-api";
import { ApiError } from "@/lib/api";

export function ProjectSync() {
  const [search, setSearch] = useState("");
  const [submittedSearch, setSubmittedSearch] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const queryClient = useQueryClient();

  const syncedQuery = useQuery({ queryKey: ["synced-projects"], queryFn: fetchSyncedProjects });

  const searchQuery = useQuery({
    queryKey: ["gitlab-projects", submittedSearch],
    queryFn: () => searchGitLabProjects(submittedSearch),
    enabled: submittedSearch.length > 0,
  });

  const syncMutation = useMutation({
    mutationFn: syncProject,
    onSuccess: (result) => {
      setWarnings(result.warnings);
      queryClient.invalidateQueries({ queryKey: ["synced-projects"] });
      queryClient.invalidateQueries({ queryKey: ["gitlab-projects"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) => setSyncedProjectActive(id, isActive),
    onSuccess: (result) => {
      setWarnings(result.warnings);
      queryClient.invalidateQueries({ queryKey: ["synced-projects"] });
    },
  });

  const activeProjects = (syncedQuery.data ?? []).filter((p) => p.is_active);
  const inactiveProjects = (syncedQuery.data ?? []).filter((p) => !p.is_active);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Synced projects</CardTitle>
        <CardDescription>
          Pick which GitLab projects this tool aggregates. GitLab stays the source of truth —
          unsyncing a project just stops it showing up here, it doesn&apos;t touch GitLab.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmittedSearch(search.trim());
          }}
        >
          <Input
            placeholder="Search GitLab projects by name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Button type="submit" variant="outline">
            Search
          </Button>
        </form>

        {warnings.length > 0 && (
          <div className="rounded-md border border-amber-400/50 bg-amber-400/10 p-3 text-sm text-amber-700 dark:text-amber-400">
            {warnings.map((w) => (
              <p key={w}>{w}</p>
            ))}
          </div>
        )}

        {syncMutation.isError && (
          <p className="text-sm text-destructive">
            {syncMutation.error instanceof ApiError ? syncMutation.error.message : "Failed to sync project"}
          </p>
        )}

        {submittedSearch && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Search results</p>
            {searchQuery.isLoading && <p className="text-sm text-muted-foreground">Searching…</p>}
            {searchQuery.isError && (
              <p className="text-sm text-destructive">
                Could not reach GitLab — check the connection status above.
              </p>
            )}
            {searchQuery.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">No projects found for &quot;{submittedSearch}&quot;.</p>
            )}
            {searchQuery.data?.map((project) => (
              <div key={project.gitlab_project_id} className="flex items-center justify-between rounded-md border p-3">
                <div>
                  <p className="text-sm font-medium">{project.name}</p>
                  <p className="text-xs text-muted-foreground">{project.full_path}</p>
                </div>
                {project.already_synced ? (
                  <Badge variant="secondary">Already synced</Badge>
                ) : (
                  <Button
                    size="sm"
                    disabled={syncMutation.isPending}
                    onClick={() => syncMutation.mutate(project.gitlab_project_id)}
                  >
                    Sync
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}

        <Separator />

        <div className="space-y-2">
          <p className="text-sm font-medium">Currently syncing ({activeProjects.length})</p>
          {syncedQuery.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {activeProjects.length === 0 && !syncedQuery.isLoading && (
            <p className="text-sm text-muted-foreground">No projects synced yet — search above to add one.</p>
          )}
          {activeProjects.map((project) => (
            <SyncedProjectRow
              key={project.id}
              project={project}
              onToggle={() => toggleMutation.mutate({ id: project.id, isActive: false })}
              pending={toggleMutation.isPending}
            />
          ))}
        </div>

        {inactiveProjects.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Unsynced ({inactiveProjects.length})</p>
            {inactiveProjects.map((project) => (
              <SyncedProjectRow
                key={project.id}
                project={project}
                onToggle={() => toggleMutation.mutate({ id: project.id, isActive: true })}
                pending={toggleMutation.isPending}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SyncedProjectRow({
  project,
  onToggle,
  pending,
}: {
  project: SyncedProject;
  onToggle: () => void;
  pending: boolean;
}) {
  return (
    <div className="flex items-center justify-between rounded-md border p-3">
      <div>
        <p className="text-sm font-medium">{project.name}</p>
        <p className="text-xs text-muted-foreground">
          {project.full_path} ·{" "}
          {project.is_active
            ? project.last_synced_at
              ? `last synced ${new Date(project.last_synced_at).toLocaleString()}`
              : "sync pending…"
            : "not syncing"}
          {project.is_active && !project.uses_work_items_api && " · classic Issues API fallback"}
          {project.is_active && !project.webhook_registered && " · webhook not registered"}
        </p>
      </div>
      <Button size="sm" variant={project.is_active ? "outline" : "default"} disabled={pending} onClick={onToggle}>
        {project.is_active ? "Unsync" : "Resync"}
      </Button>
    </div>
  );
}
