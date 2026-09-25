export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return response.json() as Promise<T>;
}

export type InToolRole = "engineer" | "manager" | "exec" | "admin";

export interface CurrentUser {
  id: string;
  name: string;
  email: string;
  gitlab_username: string;
  avatar_url: string | null;
  in_tool_role: InToolRole;
}

export function fetchCurrentUser(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/api/auth/me");
}

export function loginUrl(): string {
  return `${API_BASE_URL}/api/auth/login`;
}

export function homePathForRole(role: InToolRole): string {
  switch (role) {
    case "engineer":
      return "/my-work";
    case "manager":
      return "/team-board";
    case "exec":
      return "/radar";
    case "admin":
      return "/settings";
  }
}
