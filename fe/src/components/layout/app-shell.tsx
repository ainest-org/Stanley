"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { useCurrentUser } from "@/hooks/use-current-user";
import type { InToolRole } from "@/lib/api";

const NAV_ITEMS: { href: string; label: string; roles: InToolRole[] }[] = [
  { href: "/my-work", label: "My Work", roles: ["engineer", "manager", "admin"] },
  { href: "/team-board", label: "Team Board", roles: ["manager", "admin"] },
  { href: "/radar", label: "Exec Radar", roles: ["exec", "admin"] },
  { href: "/settings", label: "Settings", roles: ["admin"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: user } = useCurrentUser();
  const pathname = usePathname();

  const visibleNav = NAV_ITEMS.filter((item) => !user || item.roles.includes(user.in_tool_role));

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 border-r p-4 flex flex-col gap-4">
        <span className="font-semibold">PM Tool</span>
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
        </div>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
