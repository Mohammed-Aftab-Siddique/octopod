export interface WeekOffOption {
  value: number;
  label: string;
}

/** Two consecutive week-off days, starting on the given ISO weekday. */
export const WEEK_OFF_OPTIONS: WeekOffOption[] = [
  { value: 5, label: "Sat – Sun" },
  { value: 6, label: "Sun – Mon" },
  { value: 0, label: "Mon – Tue" },
  { value: 1, label: "Tue – Wed" },
  { value: 2, label: "Wed – Thu" },
  { value: 3, label: "Thu – Fri" },
  { value: 4, label: "Fri – Sat" },
];

export function weekOffLabel(startDay: number): string {
  return WEEK_OFF_OPTIONS.find((option) => option.value === startDay)?.label ?? "Mon – Tue";
}
