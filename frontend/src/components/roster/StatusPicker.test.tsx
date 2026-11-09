import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StatusPicker } from "@/components/roster/StatusPicker";
import type { ShiftStatus } from "@/lib/types";

const statuses: ShiftStatus[] = [
  {
    id: 1,
    code: "G",
    label: "General",
    color: "#E5E7EB",
    text_color: "#111827",
    is_working: true,
    sort_order: 1,
  },
  {
    id: 2,
    code: "M",
    label: "Morning",
    color: "#BBF7D0",
    text_color: "#14532D",
    is_working: true,
    sort_order: 2,
  },
];

describe("StatusPicker", () => {
  it("selects a status and closes", () => {
    const onSelect = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <StatusPicker
        open
        onOpenChange={onOpenChange}
        employeeName="Employee One"
        dateLabel="Mon 2 Nov"
        statuses={statuses}
        currentCode="G"
        onSelect={onSelect}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Morning/ }));
    expect(onSelect).toHaveBeenCalledWith("M");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
