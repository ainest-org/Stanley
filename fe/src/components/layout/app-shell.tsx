"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { useCurrentUser } from "@/hooks/use-current-user";
import { CreateWorkItemDialog } from "@/components/dashboard/create-work-item-dialog";
import { apiFetch, type InToolRole } from "@/lib/api";

const NAV_ITEMS: { href: string; label: string; roles: InToolRole[] }[] = [
  { href: "/my-work", label: "My Work", roles: ["engineer", "manager", "admin"] },
  { href: "/team-board", label: "Team Board", roles: ["manager", "admin"] },
  { href: "/standups", label: "Standups", roles: ["manager", "admin"] },
  { href: "/radar", label: "Exec Radar", roles: ["exec", "admin"] },
  { href: "/settings", label: "Settings", roles: ["admin"] },
];

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
    <div className="flex min-h-screen">
      <aside className="w-56 border-r p-4 flex flex-col gap-4">
        <span className="font-semibold">Stanley</span>
        <CreateWorkItemDialog />
        <nav className="flex flex-col gap-1">
          {visibleNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded px-2 py-1.5 text-sm ${
                pathname === item.href ? "bg-muted font-medium" : "text-muted-foreground hover:bg-muted"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto">
          <Separator className="mb-3" />
          {user && (
            <div className="flex items-center gap-2 text-sm">
              <Avatar className="h-6 w-6">
                <AvatarImage src={user.avatar_url ?? undefined} alt={user.name} />
                <AvatarFallback>{user.name.slice(0, 1)}</AvatarFallback>
              </Avatar>
              <span className="truncate">{user.name}</span>
            </div>
          )}
          <button
            type="button"
            onClick={signOut}
            className="mt-3 w-full rounded px-2 py-1.5 text-left text-sm text-muted-foreground hover:bg-muted"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
