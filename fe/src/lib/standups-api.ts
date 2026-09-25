import { apiFetch } from "@/lib/api";

export interface StandupPerson {
  user_id: string;
  name: string;
  avatar_url: string | null;
  following: boolean;
  did: string;
  doing: string;
  blockers: string;
  submitted_at: string;
}

export interface StandupBlocker {
  source: "check_in" | "flag";
  person: string | null;
  text: string;
  title?: string;
  project_name?: string;
  web_url?: string;
  work_item_id?: string;
}

export interface Standups {
  date: string;
  scope: "all" | "following";
  following_count: number;
  submitted: StandupPerson[];
  no_check_in: { user_id: string; name: string; following: boolean }[];
  blockers: StandupBlocker[];
}

export const fetchStandups = (day: string, scope: "all" | "following") =>
  apiFetch<Standups>(`/api/standups?day=${day}&scope=${scope}`);

export const setFollow = (personId: string, following: boolean) =>
  apiFetch(`/api/standups/follows/${personId}`, { method: "PUT", body: JSON.stringify({ following }) });
