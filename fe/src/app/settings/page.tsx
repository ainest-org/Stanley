"use client";

import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { ConnectionStatus } from "@/components/settings/connection-status";
import { ProjectSync } from "@/components/settings/project-sync";
import { MembersTable } from "@/components/settings/members-table";
import { HealthThresholds } from "@/components/settings/health-thresholds";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function SettingsPage() {
  return (
    <AppShell>
      <PageHeader title="Settings" description="Connect GitLab, choose what to sync, assign roles and tune the rules." />

      <div className="max-w-5xl space-y-6">
        <ConnectionStatus />

        <Tabs defaultValue="projects">
          <TabsList>
            <TabsTrigger value="projects">Projects</TabsTrigger>
            <TabsTrigger value="members">Members</TabsTrigger>
            <TabsTrigger value="rules">Rules</TabsTrigger>
          </TabsList>
          <TabsContent value="projects" className="mt-4">
            <ProjectSync />
          </TabsContent>
          <TabsContent value="members" className="mt-4">
            <MembersTable />
          </TabsContent>
          <TabsContent value="rules" className="mt-4">
            <HealthThresholds />
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
