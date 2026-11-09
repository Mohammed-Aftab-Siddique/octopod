import { describe, expect, it } from "vitest";

import { rosterFilename } from "@/lib/export";
import type { RosterGrid } from "@/lib/types";

function gridFixture(overrides: Partial<RosterGrid> = {}): RosterGrid {
  return {
    id: 1,
    year: 2026,
    month: 3,
    version: 2,
    status: "published",
    days: [],
    employees: [],
    statuses: [],
    assignments: [],
    updated_at: "2026-03-01T00:00:00Z",
    published_at: null,
    ...overrides,
  };
}

describe("rosterFilename", () => {
  it("uses the year, zero-padded month, and version", () => {
    expect(rosterFilename(gridFixture())).toBe("roster-2026-03-v2.png");
  });

  it("keeps two-digit months unchanged", () => {
    expect(rosterFilename(gridFixture({ month: 11, version: 10 }))).toBe(
      "roster-2026-11-v10.png",
    );
  });
});
