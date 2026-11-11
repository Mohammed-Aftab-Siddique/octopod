export type Role = "admin" | "employee";

export interface User {
  id: number;
  email: string;
  role: Role;
  employee_id: number | null;
  full_name: string | null;
  employee_code: string | null;
}

export interface LoginResponse {
  user: User;
  csrf_token: string;
}

export interface MeResponse {
  user: User;
  csrf_token: string;
}

export interface Employee {
  id: number;
  employee_code: string;
  full_name: string;
  email: string;
  is_active: boolean;
  rotation_offset: number;
  default_shift: string | null;
  week_off_start_day: number;
  created_at: string;
}

export interface EmployeeLookup {
  employee_code: string;
  full_name: string;
}

export type AvailabilityKind = "leave" | "comp_off" | "unavailable";

export interface Availability {
  id: number;
  employee_id: number;
  date: string;
  kind: AvailabilityKind;
  note: string | null;
  created_at: string;
}

export interface ShiftStatus {
  id: number;
  code: string;
  label: string;
  color: string;
  text_color: string;
  is_working: boolean;
  sort_order: number;
}

export type RosterStatus = "draft" | "published" | "archived";

export interface RosterSummary {
  id: number;
  year: number;
  month: number;
  version: number;
  status: RosterStatus;
  created_at: string;
  published_at: string | null;
}

export interface RosterDay {
  date: string;
  day: number;
  weekday: number;
  weekday_label: string;
  is_weekend: boolean;
  holiday: string | null;
}

export interface RosterEmployee {
  id: number;
  employee_code: string;
  full_name: string;
}

export interface RosterAssignment {
  employee_id: number;
  date: string;
  status_code: string;
  note?: string | null;
}

export interface RosterGrid {
  id: number;
  year: number;
  month: number;
  version: number;
  status: RosterStatus;
  days: RosterDay[];
  employees: RosterEmployee[];
  statuses: ShiftStatus[];
  assignments: RosterAssignment[];
  updated_at: string;
  published_at: string | null;
}

export interface Shortage {
  date: string;
  status_code: string;
  required: number;
  assigned: number;
}

export interface GenerationResult {
  roster: RosterGrid;
  shortages: Shortage[];
  warnings: string[];
}

export interface StaffingRequirement {
  status_code: string;
  required_count: number;
}

export interface Holiday {
  id: number;
  date: string;
  label: string;
}
