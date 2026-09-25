import { cn } from "@/lib/utils";

const TONES = {
  neutral: "bg-secondary text-secondary-foreground",
  info: "bg-blue-100 text-blue-800 dark:bg-blue-500/20 dark:text-blue-200",
  success: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200",
  warning: "bg-amber-100 text-amber-900 dark:bg-amber-500/20 dark:text-amber-200",
  danger: "bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-200",
} as const;

export type Tone = keyof typeof TONES;

/** A small coloured pill. Colour carries meaning: red = needs action, amber = watch out, green = good. */
export function StatusBadge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
