import { describe, expect, it } from "vitest";

import type { Employee } from "@/lib/types";
import { sortEmployees } from "./employeeSort";

const employees: Employee[] = [
  {
    id: 3,
    employee_code: "E010",
    full_name: "Zara",
    email: "zara@example.com",
    is_active: true,
    rotation_offset: 2,
    default_shift: null,
    week_off_start_day: 5,
    created_at: "2026-11-01T00:00:00Z",
  },
  {
    id: 1,
    employee_code: "E002",
    full_name: "Amy",
    email: "amy@example.com",
    is_active: true,
    rotation_offset: 0,
    default_shift: null,
    week_off_start_day: 0,
    created_at: "2026-11-01T00:00:00Z",
  },
  {
    id: 2,
    employee_code: "E003",
    full_name: "Bob",
    email: "bob@example.com",
    is_active: true,
    rotation_offset: 1,
    default_shift: null,
    week_off_start_day: 1,
    created_at: "2026-11-01T00:00:00Z",
  },
];

const names = (items: Employee[]) => items.map((item) => item.full_name);

describe("sortEmployees", () => {
  it("sorts by name", () => {
    expect(names(sortEmployees(employees, "name"))).toEqual(["Amy", "Bob", "Zara"]);
  });

  it("sorts by employee ID code", () => {
    expect(names(sortEmployees(employees, "id"))).toEqual(["Amy", "Bob", "Zara"]);
  });

  it("does not mutate the input list", () => {
    const original = [...employees];
    sortEmployees(employees, "name");
    expect(employees).toEqual(original);
  });
});
