export function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 60) return `${Math.max(minutes, 0)}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export const MR_STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  open: "Open",
  approved: "Approved",
  pipeline_failing: "Pipeline failing",
  merged: "Merged",
};
