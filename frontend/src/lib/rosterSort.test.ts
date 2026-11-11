import { describe, expect, it } from "vitest";

import type {
  RosterAssignment,
  RosterEmployee,
  ShiftStatus,
} from "@/lib/types";
import { employeeShiftCodes, sortRosterEmployees } from "./rosterSort";

const statuses: ShiftStatus[] = [
  {
    id: 1,
    code: "G",
    label: "General",
    color: "",
    text_color: "",
    is_working: true,
    sort_order: 1,
  },
  {
    id: 2,
    code: "M",
    label: "Morning",
    color: "",
    text_color: "",
    is_working: true,
    sort_order: 2,
  },
  {
    id: 3,
    code: "A",
    label: "Afternoon",
    color: "",
    text_color: "",
    is_working: true,
    sort_order: 3,
  },
  {
    id: 4,
    code: "N",
    label: "Night",
    color: "",
    text_color: "",
    is_working: true,
    sort_order: 4,
  },
  {
    id: 5,
    code: "O",
    label: "Week-off",
    color: "",
    text_color: "",
    is_working: false,
    sort_order: 5,
  },
];

const employees: RosterEmployee[] = [
  { id: 3, employee_code: "E002", full_name: "Bob" },
  { id: 1, employee_code: "E003", full_name: "Charlie" },
  { id: 2, employee_code: "E001", full_name: "Alice" },
  { id: 4, employee_code: "E004", full_name: "Dana" },
];

function assignment(
  employee_id: number,
  status_code: string,
  date: string,
): RosterAssignment {
  return { employee_id, date, status_code };
}

const assignments: RosterAssignment[] = [
  assignment(1, "M", "2026-11-01"),
  assignment(1, "M", "2026-11-02"),
  assignment(1, "G", "2026-11-03"),
  assignment(1, "O", "2026-11-04"),
  assignment(2, "A", "2026-11-01"),
  assignment(2, "A", "2026-11-02"),
  assignment(2, "N", "2026-11-03"),
  assignment(3, "G", "2026-11-01"),
  assignment(3, "G", "2026-11-02"),
];

const names = (items: RosterEmployee[]) => items.map((item) => item.full_name);

describe("sortRosterEmployees", () => {
  it("sorts by dominant shift in G, M, A, N order", () => {
    expect(
      names(sortRosterEmployees(employees, assignments, statuses, "shift")),
    ).toEqual(["Bob", "Charlie", "Alice", "Dana"]);
  });

  it("sorts by name", () => {
    expect(
      names(sortRosterEmployees(employees, assignments, statuses, "name")),
    ).toEqual(["Alice", "Bob", "Charlie", "Dana"]);
  });

  it("sorts by employee ID", () => {
    expect(
      names(sortRosterEmployees(employees, assignments, statuses, "id")),
    ).toEqual(["Alice", "Bob", "Charlie", "Dana"]);
  });

  it("keeps the original order for the default sort", () => {
    const result = sortRosterEmployees(
      employees,
      assignments,
      statuses,
      "default",
    );
    expect(result).toBe(employees);
  });
});

describe("employeeShiftCodes", () => {
  it("ignores non-working statuses and breaks ties by status order", () => {
    const tie: RosterEmployee[] = [
      { id: 9, employee_code: "E009", full_name: "Eve" },
    ];
    const tieAssignments = [
      assignment(9, "M", "2026-11-01"),
      assignment(9, "G", "2026-11-02"),
      assignment(9, "O", "2026-11-03"),
    ];

    expect(employeeShiftCodes(tie, tieAssignments, statuses).get(9)).toBe("G");
  });
});
