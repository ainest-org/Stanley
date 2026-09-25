"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Activity, ClipboardList, LayoutList, LogOut, Settings, Users, type LucideIcon } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useCurrentUser } from "@/hooks/use-current-user";
import { RefreshButton } from "@/components/layout/refresh-button";
import { CreateWorkItemDialog } from "@/components/dashboard/create-work-item-dialog";
import { apiFetch, type InToolRole } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV_ITEMS: { href: string; label: string; icon: LucideIcon; roles: InToolRole[] }[] = [
  { href: "/my-work", label: "My Work", icon: LayoutList, roles: ["engineer", "manager", "admin"] },
  { href: "/team-board", label: "Team Board", icon: Users, roles: ["manager", "admin"] },
  { href: "/standups", label: "Standups", icon: ClipboardList, roles: ["manager", "admin"] },
  { href: "/radar", label: "Exec Radar", icon: Activity, roles: ["exec", "admin"] },
  { href: "/settings", label: "Settings", icon: Settings, roles: ["admin"] },
];

const ROLE_LABEL: Record<InToolRole, string> = {
  engineer: "Engineer",
  manager: "Manager",
  exec: "Executive",
  admin: "Admin",
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: user } = useCurrentUser();
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();

  async function signOut() {
    await apiFetch("/api/auth/logout", { method: "POST" });
    queryClient.clear();
    router.replace("/");
  }

  const visibleNav = NAV_ITEMS.filter((item) => !user || item.roles.includes(user.in_tool_role));

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col gap-5 border-r bg-sidebar p-4 md:flex">
        <div className="flex items-center gap-2 px-1">
          <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
            S
          </span>
          <span className="text-base font-semibold tracking-tight">Stanley</span>
        </div>

        <CreateWorkItemDialog />

        <nav className="flex flex-col gap-0.5">
          {visibleNav.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                  active
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <item.icon className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto space-y-3">
          <RefreshButton />
          {user && (
            <div className="flex items-center gap-2.5 rounded-lg border bg-card p-2">
              <Avatar className="size-8">
                <AvatarImage src={user.avatar_url ?? undefined} alt={user.name} />
                <AvatarFallback>{user.name.slice(0, 1)}</AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium leading-tight">{user.name}</p>
                <p className="text-xs text-muted-foreground">{ROLE_LABEL[user.in_tool_role]}</p>
              </div>
              <button
                type="button"
                onClick={signOut}
                title="Sign out"
                className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <LogOut className="size-4" />
              </button>
            </div>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 overflow-x-auto border-b bg-sidebar px-3 py-2 md:hidden">
          <span className="mr-2 text-sm font-semibold">Stanley</span>
          {visibleNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-sm",
                pathname === item.href ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground",
              )}
            >
              <item.icon className="size-3.5" />
              {item.label}
            </Link>
          ))}
        </header>
        <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}
