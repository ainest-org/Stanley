"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchCurrentUser, homePathForRole } from "@/lib/api";

export default function AuthCompletePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCurrentUser()
      .then((user) => router.replace(homePathForRole(user.in_tool_role)))
      .catch(() => setError("Could not complete sign-in. Please try again."));
  }, [router]);

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <p className="text-sm text-muted-foreground">{error ?? "Signing you in…"}</p>
    </main>
  );
}
