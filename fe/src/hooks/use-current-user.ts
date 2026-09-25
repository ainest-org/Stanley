"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchCurrentUser } from "@/lib/api";

export function useCurrentUser() {
  return useQuery({
    queryKey: ["current-user"],
    queryFn: fetchCurrentUser,
    retry: false,
  });
}
