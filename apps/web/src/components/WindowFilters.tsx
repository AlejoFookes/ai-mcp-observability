import type { ReactNode } from "react";

interface WindowFiltersProps {
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
  children?: ReactNode;
}

export function WindowFilters({
  from,
  to,
  onFromChange,
  onToChange,
  children,
}: WindowFiltersProps) {
  return (
    <div className="flex flex-wrap items-end gap-4 border-b border-[var(--line)] pb-4">
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--muted)]">From (inclusive)</span>
        <input
          type="datetime-local"
          value={from}
          onChange={(event) => onFromChange(event.target.value)}
          className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-[var(--muted)]">To (exclusive)</span>
        <input
          type="datetime-local"
          value={to}
          onChange={(event) => onToChange(event.target.value)}
          className="rounded border border-[var(--line)] bg-[var(--panel)] px-3 py-2"
        />
      </label>
      {children}
    </div>
  );
}
