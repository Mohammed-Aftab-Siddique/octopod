import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ShiftStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export function StatusPicker({
  open,
  onOpenChange,
  employeeName,
  dateLabel,
  statuses,
  currentCode,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employeeName: string;
  dateLabel: string;
  statuses: ShiftStatus[];
  currentCode?: string;
  onSelect: (code: string) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Set status</DialogTitle>
          <DialogDescription>
            {employeeName} · {dateLabel}
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-2">
          {statuses.map((status) => (
            <button
              key={status.code}
              type="button"
              onClick={() => {
                onSelect(status.code);
                onOpenChange(false);
              }}
              className={cn(
                "flex items-center gap-3 rounded-md border p-2.5 text-left text-sm transition-transform hover:scale-[1.01] focus:outline-none focus:ring-2 focus:ring-ring",
                currentCode === status.code && "ring-2 ring-primary",
              )}
            >
              <span
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded text-xs font-bold"
                style={{ backgroundColor: status.color, color: status.text_color }}
              >
                {status.code}
              </span>
              <span className="font-medium">{status.label}</span>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
