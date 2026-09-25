import { AppShell } from "@/components/layout/app-shell";
import { ConnectionStatus } from "@/components/settings/connection-status";
import { ProjectSync } from "@/components/settings/project-sync";
import { MembersTable } from "@/components/settings/members-table";
import { HealthThresholds } from "@/components/settings/health-thresholds";

export default function SettingsPage() {
  return (
    <AppShell>
      <div className="space-y-6 max-w-4xl">
        <div>
          <h1 className="text-xl font-semibold mb-1">Settings</h1>
          <p className="text-sm text-muted-foreground">
            GitLab connection, project sync, member roles, and health-rule thresholds.
          </p>
        </div>
        <ConnectionStatus />
        <ProjectSync />
        <MembersTable />
        <HealthThresholds />
      </div>
    </AppShell>
  );
}
