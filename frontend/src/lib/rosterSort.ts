import type {
  RosterAssignment,
  RosterEmployee,
  ShiftStatus,
} from "@/lib/types";

export type RosterSortKey = "default" | "shift" | "name" | "id";

export const ROSTER_SORT_OPTIONS: Array<{
  value: RosterSortKey;
  label: string;
}> = [
  { value: "default", label: "Default order" },
  { value: "shift", label: "Shift (G → M → A → N)" },
  { value: "name", label: "Name (A → Z)" },
  { value: "id", label: "ID (ascending)" },
];

const PREFERRED_SHIFT_ORDER = ["G", "M", "A", "N"];

function preferredShiftRank(code: string | undefined): number {
  if (!code) return Number.MAX_SAFE_INTEGER;
  const index = PREFERRED_SHIFT_ORDER.indexOf(code);
  return index === -1 ? PREFERRED_SHIFT_ORDER.length : index;
}

function compareText(a: string, b: string): number {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
}

/**
 * Determine each employee's main shift for the roster period.
 *
 * The shift an employee works most often is treated as their shift. Ties are
 * broken by the configured status order, then by the status code so the result
 * is deterministic. Non-working statuses (week-offs, leave, holidays) never
 * decide the shift.
 */
export function employeeShiftCodes(
  employees: RosterEmployee[],
  assignments: RosterAssignment[],
  statuses: ShiftStatus[],
): Map<number, string> {
  const workingByCode = new Map<string, ShiftStatus>();
  for (const status of statuses) {
    if (status.is_working) workingByCode.set(status.code, status);
  }

  const counts = new Map<number, Map<string, number>>();
  for (const assignment of assignments) {
    if (!workingByCode.has(assignment.status_code)) continue;
    const employeeCounts =
      counts.get(assignment.employee_id) ?? new Map<string, number>();
    employeeCounts.set(
      assignment.status_code,
      (employeeCounts.get(assignment.status_code) ?? 0) + 1,
    );
    counts.set(assignment.employee_id, employeeCounts);
  }

  const shifts = new Map<number, string>();
  for (const employee of employees) {
    const employeeCounts = counts.get(employee.id);
    if (!employeeCounts || employeeCounts.size === 0) continue;

    let bestCode: string | undefined;
    let bestCount = -1;
    for (const [code, count] of employeeCounts) {
      const currentStatus = workingByCode.get(code);
      const bestStatus = bestCode ? workingByCode.get(bestCode) : undefined;
      const better =
        count > bestCount ||
        (count === bestCount &&
          (currentStatus?.sort_order ?? Number.MAX_SAFE_INTEGER) <
            (bestStatus?.sort_order ?? Number.MAX_SAFE_INTEGER)) ||
        (count === bestCount &&
          currentStatus?.sort_order === bestStatus?.sort_order &&
          compareText(code, bestCode ?? "") < 0);
      if (better) {
        bestCode = code;
        bestCount = count;
      }
    }
    if (bestCode) shifts.set(employee.id, bestCode);
  }
  return shifts;
}

export function sortRosterEmployees(
  employees: RosterEmployee[],
  assignments: RosterAssignment[],
  statuses: ShiftStatus[],
  sortKey: RosterSortKey,
): RosterEmployee[] {
  if (sortKey === "default") return employees;

  const shifts = employeeShiftCodes(employees, assignments, statuses);
  const byName = (a: RosterEmployee, b: RosterEmployee) =>
    compareText(a.full_name, b.full_name) ||
    compareText(a.employee_code, b.employee_code);

  return [...employees].sort((a, b) => {
    if (sortKey === "name") return byName(a, b);
    if (sortKey === "id") {
      return compareText(a.employee_code, b.employee_code) || a.id - b.id;
    }

    const shiftA = shifts.get(a.id);
    const shiftB = shifts.get(b.id);
    const rankDifference =
      preferredShiftRank(shiftA) - preferredShiftRank(shiftB);
    if (rankDifference !== 0) return rankDifference;
    if (shiftA !== shiftB) return compareText(shiftA ?? "", shiftB ?? "");
    return byName(a, b);
  });
}
