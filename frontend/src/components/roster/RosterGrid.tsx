import type { RosterAssignment, RosterDay, RosterEmployee, RosterGrid as Grid, ShiftStatus } from "@/lib/types";
import { cn, todayIso } from "@/lib/utils";

interface RosterGridProps {
  grid: Grid;
  editable?: boolean;
  employeeFilterId?: number | null;
  highlightEmployeeId?: number | null;
  onEdit?: (employee: RosterEmployee, day: RosterDay, currentCode?: string) => void;
}

export function RosterGrid({
  grid,
  editable = false,
  employeeFilterId = null,
  highlightEmployeeId = null,
  onEdit,
}: RosterGridProps) {
  const statusByCode = new Map<string, ShiftStatus>(
    grid.statuses.map((status) => [status.code, status]),
  );
  const assignmentMap = new Map<string, RosterAssignment>();
  for (const assignment of grid.assignments) {
    assignmentMap.set(`${assignment.employee_id}:${assignment.date}`, assignment);
  }

  const employees = employeeFilterId
    ? grid.employees.filter((employee) => employee.id === employeeFilterId)
    : grid.employees;
  const today = todayIso();

  return (
    <div className="scrollbar-thin max-h-[76vh] overflow-auto rounded-lg border bg-card">
      <table className="w-max border-collapse text-xs">
        <caption className="sr-only">
          {grid.status === "draft" ? "Draft" : "Published"} roster for {grid.employees.length}{" "}
          employees across {grid.days.length} days
        </caption>
        <thead>
          <tr>
            <th
              scope="col"
              className="sticky left-0 top-0 z-30 w-[190px] min-w-[190px] border-b border-r bg-slate-50 px-3 py-2 text-left align-middle text-[11px] font-semibold uppercase tracking-wide text-muted-foreground"
            >
              Employee
            </th>
            {grid.days.map((day) => (
              <th
                key={day.date}
                scope="col"
                title={day.holiday ?? day.weekday_label}
                className={cn(
                  "sticky top-0 z-20 w-[46px] min-w-[46px] border-b border-r px-0.5 py-1 text-center align-middle font-medium",
                  day.holiday
                    ? "bg-violet-200 text-violet-950"
                    : day.is_weekend
                      ? "bg-amber-100 text-amber-950"
                      : "bg-slate-50 text-slate-700",
                  day.date === today && "ring-2 ring-inset ring-primary",
                )}
              >
                <span className="block text-[13px] font-bold leading-4">{day.day}</span>
                <span className="block text-[10px] uppercase leading-4 opacity-70">
                  {day.holiday ? "HOL" : day.weekday_label.slice(0, 3)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {employees.map((employee, rowIndex) => (
            <tr
              key={employee.id}
              className={cn(
                rowIndex % 2 === 1 && "bg-slate-50/60",
                highlightEmployeeId === employee.id && "bg-primary/10",
              )}
            >
              <th
                scope="row"
                className={cn(
                  "sticky left-0 z-10 border-b border-r px-3 py-1.5 text-left align-middle font-medium",
                  rowIndex % 2 === 1 ? "bg-slate-50" : "bg-card",
                  highlightEmployeeId === employee.id && "bg-blue-50",
                )}
              >
                <span className="block max-w-[170px] truncate text-[13px]" title={employee.full_name}>
                  {employee.full_name}
                </span>
                <span className="block text-[10px] text-muted-foreground">
                  {employee.employee_code}
                </span>
              </th>
              {grid.days.map((day) => {
                const assignment = assignmentMap.get(`${employee.id}:${day.date}`);
                const status = assignment ? statusByCode.get(assignment.status_code) : undefined;
                const label = `${employee.full_name}, ${day.weekday_label} ${day.day}${
                  status ? `, ${status.label}` : ", unassigned"
                }`;
                const title = assignment
                  ? `${employee.full_name} · ${day.weekday_label} ${day.day} · ${
                      status?.label ?? assignment.status_code
                    }${assignment.note ? ` · ${assignment.note}` : ""}`
                  : `${employee.full_name} · ${day.weekday_label} ${day.day}`;
                const cellStyle = status
                  ? { backgroundColor: status.color, color: status.text_color }
                  : undefined;
                return (
                  <td
                    key={day.date}
                    className="border-b border-r p-0"
                    style={cellStyle}
                  >
                    {editable ? (
                      <button
                        type="button"
                        onClick={() => onEdit?.(employee, day, assignment?.status_code)}
                        title={title}
                        aria-label={label}
                        className={cn(
                          "flex h-9 w-full min-w-[46px] items-center justify-center text-[12px] font-semibold",
                          "cursor-pointer hover:opacity-75 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary",
                          !assignment && "text-muted-foreground",
                        )}
                      >
                        {assignment?.status_code ?? "+"}
                      </button>
                    ) : (
                      <div
                        className="flex h-9 w-full min-w-[46px] items-center justify-center text-[12px] font-semibold"
                        title={title}
                      >
                        <span className="sr-only">{label}</span>
                        <span aria-hidden="true">{assignment?.status_code ?? ""}</span>
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
          {employees.length === 0 ? (
            <tr>
              <td
                colSpan={grid.days.length + 1}
                className="px-3 py-10 text-center text-sm text-muted-foreground"
              >
                No employees to display.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
