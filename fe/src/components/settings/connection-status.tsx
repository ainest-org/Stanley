"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { fetchGitLabStatus } from "@/lib/admin-api";

export function ConnectionStatus() {
  const { data, isLoading } = useQuery({ queryKey: ["gitlab-status"], queryFn: fetchGitLabStatus });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          GitLab connection
          {!isLoading && data && (
            <Badge variant={data.connected ? "default" : "destructive"}>
              {data.connected ? "Connected" : "Not connected"}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>{data?.instance_url ?? "…"}</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">Checking…</p>}
        {data?.connected && <p className="text-sm text-muted-foreground">GitLab version {data.version}</p>}
        {data && !data.connected && (
          <p className="text-sm text-destructive">
            {data.error} — set <code>GITLAB_SYNC_SERVICE_TOKEN</code> in <code>BE/.env</code> and restart the backend.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
