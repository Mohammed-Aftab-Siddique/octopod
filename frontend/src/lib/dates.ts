import { format } from "date-fns";

/**
 * Parse a date-only string (`YYYY-MM-DD`) as local midnight.
 *
 * `new Date("2026-11-05")` parses as UTC and can render as the previous day in
 * negative-offset timezones, so every date-only value goes through this helper.
 */
export function parseDateOnly(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function formatDateOnly(value: string, pattern = "EEE d MMM yyyy"): string {
  return format(parseDateOnly(value), pattern);
}

export function firstDayOfMonthIso(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}-01`;
}
