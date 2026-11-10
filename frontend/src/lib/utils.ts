import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const WEEKDAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

/** The two consecutive week-off days for a start day (0 = Monday). */
export function weekOffPairLabel(startDay: number): string {
  const start = ((startDay % 7) + 7) % 7;
  return `${WEEKDAY_NAMES[start]} – ${WEEKDAY_NAMES[(start + 1) % 7]}`;
}

export const WEEK_OFF_OPTIONS = WEEKDAY_NAMES.map((_, index) => ({
  value: index,
  label: weekOffPairLabel(index),
}));

export const MONTH_NAMES = [
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

export function currentMonth(): { year: number; month: number } {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

export function monthLabel(year: number, month: number): string {
  return `${MONTH_NAMES[month - 1]} ${year}`;
}

export function shiftMonth(year: number, month: number, delta: number) {
  const date = new Date(year, month - 1 + delta, 1);
  return { year: date.getFullYear(), month: date.getMonth() + 1 };
}

export function todayIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
    now.getDate(),
  ).padStart(2, "0")}`;
}

export function statusBadgeClass(status: string): string {
  switch (status) {
    case "published":
      return "bg-emerald-100 text-emerald-800";
    case "archived":
      return "bg-slate-200 text-slate-600";
    default:
      return "bg-amber-100 text-amber-800";
  }
}
