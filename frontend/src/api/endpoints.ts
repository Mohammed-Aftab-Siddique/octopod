import { api } from "@/api/client";
import { downloadBlob } from "@/lib/download";
import { renderRosterPng, rosterFilename } from "@/lib/export";
import type {
  Availability,
  AvailabilityKind,
  Employee,
  EmployeeLookup,
  GenerationResult,
  Holiday,
  LoginResponse,
  MeResponse,
  RosterGrid,
  RosterSettings,
  RosterSummary,
  ShiftStatus,
  StaffingRequirement,
} from "@/lib/types";

export interface EmployeeInput {
  employee_code: string;
  full_name: string;
  email: string;
  default_shift?: string | null;
  password?: string;
}

export interface AvailabilityInput {
  start_date: string;
  end_date: string;
  kind: AvailabilityKind;
  note: string | null;
}

export const authApi = {
  me: () => api.get<MeResponse>("/auth/me"),
  login: (identifier: string, password: string) =>
    api.post<LoginResponse>("/auth/login", { identifier, password }),
  logout: () => api.post<{ detail: string }>("/auth/logout"),
};

export const employeesApi = {
  list: (includeInactive: boolean) =>
    api.get<Employee[]>(`/employees?include_inactive=${includeInactive ? "true" : "false"}`),
  get: (id: number) => api.get<Employee>(`/employees/${id}`),
  create: (payload: EmployeeInput) => api.post<Employee>("/employees", payload),
  update: (id: number, payload: Partial<EmployeeInput>) =>
    api.patch<Employee>(`/employees/${id}`, payload),
  deactivate: (id: number) => api.post<Employee>(`/employees/${id}/deactivate`),
  resetPassword: (id: number, password: string) =>
    api.post<void>(`/employees/${id}/reset-password`, { password }),
  lookup: (employeeCode: string) =>
    api.get<EmployeeLookup>(`/employees/lookup?employee_code=${encodeURIComponent(employeeCode)}`),
  listAvailability: (id: number, from: string, to: string) =>
    api.get<Availability[]>(`/employees/${id}/availability?from=${from}&to=${to}`),
  addAvailability: (id: number, payload: AvailabilityInput) =>
    api.post<Availability[]>(`/employees/${id}/availability`, payload),
  deleteAvailability: (id: number, availabilityId: number) =>
    api.delete<void>(`/employees/${id}/availability/${availabilityId}`),
};

export const referenceApi = {
  listStatuses: () => api.get<ShiftStatus[]>("/reference/shift-statuses"),
  listRequirements: () =>
    api.get<StaffingRequirement[]>("/reference/staffing-requirements"),
  saveRequirements: (requirements: StaffingRequirement[]) =>
    api.put<StaffingRequirement[]>("/reference/staffing-requirements", { requirements }),
  getRosterSettings: () => api.get<RosterSettings>("/reference/roster-settings"),
  saveRosterSettings: (consecutiveOffDays: number) =>
    api.put<RosterSettings>("/reference/roster-settings", {
      consecutive_off_days: consecutiveOffDays,
    }),
  listHolidays: (year: number, month: number) =>
    api.get<Holiday[]>(`/reference/holidays?year=${year}&month=${month}`),
  createHoliday: (date: string, label: string) =>
    api.post<Holiday>("/reference/holidays", { date, label }),
  deleteHoliday: (holidayId: number) => api.delete<void>(`/reference/holidays/${holidayId}`),
};

export const rostersApi = {
  list: (year: number, month: number) =>
    api.get<RosterSummary[]>(`/rosters?year=${year}&month=${month}`),
  create: (year: number, month: number) => api.post<RosterGrid>("/rosters", { year, month }),
  get: (id: number) => api.get<RosterGrid>(`/rosters/${id}`),
  delete: (id: number) => api.delete<void>(`/rosters/${id}`),
  patchAssignments: (
    id: number,
    assignments: { employee_id: number; date: string; status_code: string }[],
  ) => api.patch<RosterGrid>(`/rosters/${id}/assignments`, { assignments }),
  generate: (id: number) => api.post<GenerationResult>(`/rosters/${id}/generate`),
  publish: (id: number) => api.post<RosterGrid>(`/rosters/${id}/publish`),
  myRoster: (year: number, month: number) =>
    api.get<RosterGrid>(`/me/roster?year=${year}&month=${month}`),
  downloadExport: async (id: number, grid?: RosterGrid): Promise<void> => {
    const roster = grid ?? (await api.get<RosterGrid>(`/rosters/${id}`));
    const blob = await renderRosterPng(roster);
    downloadBlob(blob, rosterFilename(roster));
  },
};
