import type { ShiftStatus } from "@/lib/types";

export function RosterLegend({ statuses }: { statuses: ShiftStatus[] }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
      <span className="font-medium text-foreground">Legend</span>
      {statuses.map((status) => (
        <span key={status.code} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-4 w-4 rounded border border-black/10"
            style={{ backgroundColor: status.color }}
          />
          <span>
            <span className="font-semibold text-foreground">{status.code}</span> {status.label}
          </span>
        </span>
      ))}
    </div>
  );
}
