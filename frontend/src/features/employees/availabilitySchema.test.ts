import { describe, expect, it } from "vitest";

import { availabilitySchema } from "@/features/employees/availabilitySchema";

describe("availability schema", () => {
  const base = {
    start_date: "2026-11-10",
    end_date: "2026-11-12",
    kind: "leave" as const,
    note: "",
  };

  it("accepts a valid range", () => {
    expect(availabilitySchema.safeParse(base).success).toBe(true);
  });

  it("rejects an inverted range", () => {
    const result = availabilitySchema.safeParse({
      ...base,
      start_date: "2026-11-12",
      end_date: "2026-11-10",
    });
    expect(result.success).toBe(false);
  });

  it("rejects ranges longer than 366 days", () => {
    const result = availabilitySchema.safeParse({
      ...base,
      start_date: "2026-01-01",
      end_date: "2027-06-01",
    });
    expect(result.success).toBe(false);
  });
});
