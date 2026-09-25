"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export interface PickOption {
  value: string;
  label: string;
}

/** shadcn Select that shows each option's label (not its raw value) in the trigger. */
export function Pick({
  value,
  onChange,
  options,
  placeholder,
  disabled,
  className,
}: {
  value: string | null;
  onChange: (value: string) => void;
  options: PickOption[];
  placeholder: string;
  disabled?: boolean;
  className?: string;
}) {
  const items = Object.fromEntries(options.map((o) => [o.value, o.label]));
  return (
    <Select
      value={value}
      items={items}
      disabled={disabled}
      onValueChange={(next) => next !== null && onChange(next as string)}
    >
      <SelectTrigger className={className ?? "w-full"}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
