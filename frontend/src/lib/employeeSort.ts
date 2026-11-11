import type { Employee } from "@/lib/types";

export type EmployeeSortKey = "name" | "id";

export const EMPLOYEE_SORT_OPTIONS: Array<{ value: EmployeeSortKey; label: string }> = [
  { value: "name", label: "Name (A → Z)" },
  { value: "id", label: "ID (ascending)" },
];

function compareText(a: string, b: string): number {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
}

export function sortEmployees(employees: Employee[], sortKey: EmployeeSortKey): Employee[] {
  return [...employees].sort((a, b) => {
    if (sortKey === "id") {
      return compareText(a.employee_code, b.employee_code) || a.id - b.id;
    }
    return compareText(a.full_name, b.full_name) || compareText(a.employee_code, b.employee_code);
  });
}
