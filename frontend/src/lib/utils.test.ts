import { describe, expect, it } from "vitest";

import { monthLabel, shiftMonth, statusBadgeClass } from "./utils";

describe("date helpers", () => {
  it("rolls over to the next year", () => {
    expect(shiftMonth(2026, 12, 1)).toEqual({ year: 2027, month: 1 });
  });

  it("rolls back to the previous year", () => {
    expect(shiftMonth(2026, 1, -1)).toEqual({ year: 2025, month: 12 });
  });

  it("formats month labels", () => {
    expect(monthLabel(2026, 11)).toBe("November 2026");
  });
});

describe("status badge classes", () => {
  it("uses distinct classes per state", () => {
    expect(statusBadgeClass("published")).toContain("emerald");
    expect(statusBadgeClass("draft")).toContain("amber");
    expect(statusBadgeClass("archived")).toContain("slate");
  });
});
