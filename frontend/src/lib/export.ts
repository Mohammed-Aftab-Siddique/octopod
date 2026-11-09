import type { RosterGrid } from "@/lib/types";

const MARGIN = 24;
const NAME_WIDTH = 230;
const DAY_WIDTH = 46;
const ROW_HEIGHT = 34;
const HEADER_DAY_HEIGHT = 30;
const HEADER_WEEKDAY_HEIGHT = 26;
const TITLE_HEIGHT = 56;
const LEGEND_ROW_HEIGHT = 34;
const LEGEND_COLUMN_WIDTH = 320;
const SCALE = 2;

const GRID_COLOR = "#D1D5DB";
const HEADER_BG = "#F9FAFB";
const TEXT_COLOR = "#111827";

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const FONT_FAMILY = '"DejaVu Sans", "Liberation Sans", Arial, sans-serif';

function font(size: number, bold = false): string {
  return `${bold ? "700" : "400"} ${size}px ${FONT_FAMILY}`;
}

function fitText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  size = 14,
): string {
  ctx.font = font(size);
  if (ctx.measureText(text).width <= maxWidth) return text;
  const ellipsis = "…";
  let trimmed = text;
  while (trimmed && ctx.measureText(trimmed + ellipsis).width > maxWidth) {
    trimmed = trimmed.slice(0, -1);
  }
  return trimmed + ellipsis;
}

function drawText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  options: {
    fill?: string;
    size?: number;
    bold?: boolean;
    align?: CanvasTextAlign;
    baseline?: CanvasTextBaseline;
  } = {},
): void {
  ctx.fillStyle = options.fill ?? TEXT_COLOR;
  ctx.font = font(options.size ?? 14, options.bold ?? false);
  ctx.textAlign = options.align ?? "left";
  ctx.textBaseline = options.baseline ?? "alphabetic";
  ctx.fillText(text, x, y);
}

function rect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  fill?: string,
): void {
  if (fill) {
    ctx.fillStyle = fill;
    ctx.fillRect(x, y, width, height);
  }
}

function line(ctx: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number) {
  ctx.strokeStyle = GRID_COLOR;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

function monthName(month: number): string {
  return MONTH_NAMES[month - 1] ?? String(month);
}

function rosterState(grid: RosterGrid): string {
  if (grid.status === "published") return "Published";
  return grid.status.charAt(0).toUpperCase() + grid.status.slice(1);
}

export function rosterFilename(grid: RosterGrid): string {
  const month = String(grid.month).padStart(2, "0");
  return `roster-${grid.year}-${month}-v${grid.version}.png`;
}

/**
 * Renders a roster grid to a PNG blob using the Canvas 2D API.
 *
 * This mirrors the previous Pillow output closely enough for a printable
 * roster while running entirely in the browser, so no Worker CPU is spent on
 * image generation.
 */
export async function renderRosterPng(grid: RosterGrid): Promise<Blob> {
  const days = grid.days.length;
  const employeeCount = Math.max(1, grid.employees.length);
  const legendRows = Math.max(1, Math.ceil((grid.statuses.length + 3) / 4));
  const width = MARGIN * 2 + NAME_WIDTH + days * DAY_WIDTH;
  const height =
    TITLE_HEIGHT +
    HEADER_DAY_HEIGHT +
    HEADER_WEEKDAY_HEIGHT +
    employeeCount * ROW_HEIGHT +
    LEGEND_ROW_HEIGHT * (legendRows + 1) +
    MARGIN;

  const canvas = document.createElement("canvas");
  canvas.width = width * SCALE;
  canvas.height = height * SCALE;

  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Unable to create a canvas rendering context");
  ctx.scale(SCALE, SCALE);

  rect(ctx, 0, 0, width, height, "#FFFFFF");

  const title = `Roster — ${monthName(grid.month)} ${grid.year}  ·  ${rosterState(grid)} v${grid.version}`;
  drawText(ctx, title, MARGIN, MARGIN / 2 + 8, { size: 22, bold: true });

  const tableTop = TITLE_HEIGHT;
  const dayTop = tableTop;
  const weekdayTop = dayTop + HEADER_DAY_HEIGHT;
  const rowsTop = weekdayTop + HEADER_WEEKDAY_HEIGHT;
  const tableRight = MARGIN + NAME_WIDTH + days * DAY_WIDTH;
  const rowsBottom = rowsTop + grid.employees.length * ROW_HEIGHT;

  // Header block.
  rect(ctx, MARGIN, dayTop, tableRight - MARGIN, rowsTop - dayTop, HEADER_BG);
  drawText(ctx, "DATE", MARGIN + 8, dayTop + 8, {
    fill: "#374151",
    bold: true,
    baseline: "top",
  });

  const statusByCode = new Map(grid.statuses.map((status) => [status.code, status]));
  const assignmentMap = new Map(
    grid.assignments.map((assignment) => [
      `${assignment.employee_id}|${assignment.date}`,
      assignment,
    ]),
  );

  grid.days.forEach((day, index) => {
    const x0 = MARGIN + NAME_WIDTH + index * DAY_WIDTH;
    if (day.holiday) {
      rect(ctx, x0, dayTop, DAY_WIDTH, rowsTop - dayTop, "#DDD6FE");
    } else if (day.is_weekend) {
      rect(ctx, x0, dayTop, DAY_WIDTH, rowsTop - dayTop, "#FEF3C7");
    }
    drawText(ctx, String(day.day), x0 + DAY_WIDTH / 2, dayTop + 6, {
      bold: true,
      align: "center",
      baseline: "top",
    });
    drawText(ctx, day.weekday_label.slice(0, 3), x0 + DAY_WIDTH / 2, weekdayTop + 4, {
      fill: "#4B5563",
      size: 11,
      align: "center",
      baseline: "top",
    });
    line(ctx, x0, dayTop, x0, rowsTop);
  });

  drawText(ctx, "EMPLOYEE", MARGIN + 8, weekdayTop + 4, {
    fill: "#4B5563",
    size: 11,
    baseline: "top",
  });
  line(ctx, MARGIN, weekdayTop, tableRight, weekdayTop);
  line(ctx, MARGIN, rowsTop, tableRight, rowsTop);

  grid.employees.forEach((employee, rowIndex) => {
    const y0 = rowsTop + rowIndex * ROW_HEIGHT;
    if (rowIndex % 2 === 1) {
      rect(ctx, MARGIN, y0, NAME_WIDTH, ROW_HEIGHT, HEADER_BG);
    }
    const name = fitText(ctx, employee.full_name, NAME_WIDTH - 16);
    drawText(ctx, name, MARGIN + 8, y0 + ROW_HEIGHT / 2, {
      baseline: "middle",
    });

    grid.days.forEach((day, dayIndex) => {
      const x0 = MARGIN + NAME_WIDTH + dayIndex * DAY_WIDTH;
      const assignment = assignmentMap.get(`${employee.id}|${day.date}`);
      if (!assignment) return;
      const status = statusByCode.get(assignment.status_code);
      rect(ctx, x0, y0, DAY_WIDTH, ROW_HEIGHT, status?.color ?? "#FFFFFF");
      drawText(ctx, assignment.status_code, x0 + DAY_WIDTH / 2, y0 + ROW_HEIGHT / 2, {
        fill: status?.text_color ?? TEXT_COLOR,
        bold: true,
        align: "center",
        baseline: "middle",
      });
    });

    line(ctx, MARGIN, y0 + ROW_HEIGHT, tableRight, y0 + ROW_HEIGHT);
    line(ctx, MARGIN, y0, MARGIN, y0 + ROW_HEIGHT);
  });

  // Cell separators.
  for (let dayIndex = 0; dayIndex <= days; dayIndex += 1) {
    const x = MARGIN + NAME_WIDTH + dayIndex * DAY_WIDTH;
    line(ctx, x, dayTop, x, rowsBottom);
  }
  line(ctx, MARGIN + NAME_WIDTH, dayTop, MARGIN + NAME_WIDTH, rowsBottom);

  // Legend.
  const legendTop = rowsBottom + 18;
  drawText(ctx, "Legend", MARGIN, legendTop, { bold: true, baseline: "top" });
  const boxSize = 16;
  let x = MARGIN;
  let y = legendTop + 22;
  grid.statuses.forEach((status, index) => {
    if (index > 0 && index % 4 === 0) {
      x = MARGIN;
      y += LEGEND_ROW_HEIGHT - 8;
    }
    rect(ctx, x, y, boxSize, boxSize, status.color);
    ctx.strokeStyle = GRID_COLOR;
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, boxSize, boxSize);
    drawText(ctx, `${status.code} — ${status.label}`, x + boxSize + 6, y + boxSize / 2, {
      fill: "#374151",
      size: 11,
      baseline: "middle",
    });
    x += LEGEND_COLUMN_WIDTH;
  });

  const generated = new Date();
  const stamp = `${generated.toISOString().slice(0, 16).replace("T", " ")} UTC`;
  drawText(ctx, `Generated ${stamp} · Octopod`, width - MARGIN, height - MARGIN + 4, {
    fill: "#6B7280",
    size: 11,
    align: "right",
    baseline: "bottom",
  });

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("Unable to encode the roster image"));
    }, "image/png");
  });
}
