import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RosterGrid } from "@/components/roster/RosterGrid";
import type { RosterGrid as Grid } from "@/lib/types";

const grid: Grid = {
  id: 1,
  year: 2026,
  month: 11,
  version: 1,
  status: "published",
  days: [
    {
      date: "2026-11-01",
      day: 1,
      weekday: 6,
      weekday_label: "Saturday",
      is_weekend: true,
      holiday: null,
    },
    {
      date: "2026-11-02",
      day: 2,
      weekday: 0,
      weekday_label: "Monday",
      is_weekend: false,
      holiday: null,
    },
  ],
  employees: [
    { id: 1, employee_code: "E001", full_name: "Employee One" },
    { id: 2, employee_code: "E002", full_name: "Employee Two" },
  ],
  statuses: [
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
      code: "O",
      label: "Week-off",
      color: "#F3F4F6",
      text_color: "#374151",
      is_working: false,
      sort_order: 2,
    },
  ],
  assignments: [
    { employee_id: 1, date: "2026-11-01", status_code: "G", note: null },
    { employee_id: 2, date: "2026-11-02", status_code: "O", note: null },
  ],
  updated_at: "2026-11-07T10:00:00Z",
  published_at: "2026-11-07T10:00:00Z",
};

describe("RosterGrid", () => {
  it("renders read-only cells without interactive buttons", () => {
    render(<RosterGrid grid={grid} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(
      screen.getByRole("rowheader", { name: /Employee One/ }),
    ).toBeInTheDocument();
    // Two rows x two days = four cells, none of which should be buttons.
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.getByText(/General/)).toBeInTheDocument();
  });

  it("calls onEdit for editable cells", () => {
    const onEdit = vi.fn();
    render(
      <RosterGrid
        grid={{ ...grid, status: "draft" }}
        editable
        onEdit={onEdit}
      />,
    );

    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(4);
    fireEvent.click(buttons[0]);
    expect(onEdit).toHaveBeenCalledWith(grid.employees[0], grid.days[0], "G");
  });

  it("filters to a single employee when requested", () => {
    render(<RosterGrid grid={grid} employeeFilterId={2} />);
    expect(
      screen.getByRole("rowheader", { name: /Employee Two/ }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("rowheader", { name: /Employee One/ }),
    ).not.toBeInTheDocument();
  });

  it("sorts rows by shift and by name", () => {
    const sortable: Grid = {
      ...grid,
      employees: [
        { id: 1, employee_code: "E002", full_name: "Zed" },
        { id: 2, employee_code: "E001", full_name: "Amy" },
      ],
      assignments: [
        { employee_id: 1, date: "2026-11-01", status_code: "G" },
        { employee_id: 2, date: "2026-11-01", status_code: "M" },
      ],
      statuses: [
        ...grid.statuses,
        {
          id: 3,
          code: "M",
          label: "Morning",
          color: "#E5E7EB",
          text_color: "#111827",
          is_working: true,
          sort_order: 3,
        },
      ],
    };

    render(<RosterGrid grid={sortable} />);
    const rows = () =>
      screen.getAllByRole("rowheader").map((row) => row.textContent ?? "");

    expect(rows()[0]).toContain("Zed");
    fireEvent.change(screen.getByLabelText("Sort roster"), {
      target: { value: "shift" },
    });
    expect(rows()[0]).toContain("Zed");

    fireEvent.change(screen.getByLabelText("Sort roster"), {
      target: { value: "name" },
    });
    expect(rows()[0]).toContain("Amy");
    expect(rows()[1]).toContain("Zed");
  });
});
