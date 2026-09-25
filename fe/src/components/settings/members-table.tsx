"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fetchMembers, updateMemberRole } from "@/lib/admin-api";
import type { InToolRole } from "@/lib/api";

const ROLE_OPTIONS: { value: InToolRole; label: string }[] = [
  { value: "engineer", label: "Engineer" },
  { value: "manager", label: "Manager" },
  { value: "exec", label: "Exec" },
  { value: "admin", label: "Admin" },
];

export function MembersTable() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["members"], queryFn: fetchMembers });

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: InToolRole }) => updateMemberRole(userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members"] }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Members</CardTitle>
        <CardDescription>
          Auto-imported from synced projects. In-tool role only decides which screens someone
          lands on — it never grants more GitLab access than their own GitLab account already has.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!isLoading && data?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No members yet — sync a project above to pull in its members.
          </p>
        )}
        {data && data.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Person</TableHead>
                <TableHead>GitLab</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>In-tool role</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((member) => (
                <TableRow key={member.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Avatar className="h-6 w-6">
                        <AvatarImage src={member.avatar_url ?? undefined} alt={member.name} />
                        <AvatarFallback>{member.name.slice(0, 1)}</AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="text-sm font-medium leading-none">{member.name}</p>
                        <p className="text-xs text-muted-foreground">{member.email}</p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">@{member.gitlab_username}</TableCell>
                  <TableCell>
                    <Badge variant={member.has_logged_in ? "default" : "secondary"}>
                      {member.has_logged_in ? "Active" : "Not signed in yet"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Select
                      value={member.in_tool_role}
                      onValueChange={(value) => roleMutation.mutate({ userId: member.id, role: value as InToolRole })}
                    >
                      <SelectTrigger className="w-36">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ROLE_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
