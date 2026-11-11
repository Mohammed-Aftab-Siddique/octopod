import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Pencil, Plus, UserMinus, UserRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { employeesApi, referenceApi } from "@/api/endpoints";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  EMPLOYEE_SORT_OPTIONS,
  sortEmployees,
  type EmployeeSortKey,
} from "@/lib/employeeSort";
import type { Employee } from "@/lib/types";
import { WEEK_OFF_OPTIONS } from "@/lib/weekOff";

const employeeSchema = z.object({
  employee_code: z
    .string()
    .min(1, "Employee ID is required")
    .max(50)
    .regex(/^[A-Za-z0-9_-]+$/, "Use letters, numbers, hyphens or underscores"),
  full_name: z.string().min(1, "Name is required").max(120),
  email: z.string().email("Enter a valid email"),
  default_shift: z.string(),
  week_off_start_day: z.coerce.number().int().min(0).max(6),
  password: z.string().min(8, "Use at least 8 characters").optional().or(z.literal("")),
});

const resetSchema = z.object({
  password: z.string().min(8, "Use at least 8 characters").max(200),
});

type EmployeeForm = z.infer<typeof employeeSchema>;
type ResetForm = z.infer<typeof resetSchema>;

export function AdminEmployeesPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Employee | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showInactive, setShowInactive] = useState(true);
  const [sortKey, setSortKey] = useState<EmployeeSortKey>("name");
  const [deactivateTarget, setDeactivateTarget] = useState<Employee | null>(null);
  const [resetTarget, setResetTarget] = useState<Employee | null>(null);

  const employeesQuery = useQuery({
    queryKey: ["employees", showInactive],
    queryFn: () => employeesApi.list(showInactive),
  });

  const statusesQuery = useQuery({
    queryKey: ["shift-statuses"],
    queryFn: () => referenceApi.listStatuses(),
  });
  const workingStatuses = (statusesQuery.data ?? []).filter((status) => status.is_working);

  const form = useForm<EmployeeForm>({
    resolver: zodResolver(employeeSchema),
    defaultValues: {
      employee_code: "",
      full_name: "",
      email: "",
      default_shift: "",
      week_off_start_day: 5,
      password: "",
    },
  });

  const resetForm = useForm<ResetForm>({
    resolver: zodResolver(resetSchema),
    defaultValues: { password: "" },
  });

  useEffect(() => {
    if (!dialogOpen) return;
    if (editing) {
      form.reset({
        employee_code: editing.employee_code,
        full_name: editing.full_name,
        email: editing.email,
        default_shift: editing.default_shift ?? "",
        week_off_start_day: editing.week_off_start_day,
        password: "",
      });
    } else {
      form.reset({
        employee_code: "",
        full_name: "",
        email: "",
        default_shift: "",
        week_off_start_day: 5,
        password: "",
      });
    }
  }, [dialogOpen, editing, form]);

  const saveMutation = useMutation({
    mutationFn: (values: EmployeeForm) => {
      const payload = {
        employee_code: values.employee_code.trim().toUpperCase(),
        full_name: values.full_name.trim(),
        email: values.email.trim(),
        default_shift: values.default_shift || null,
        week_off_start_day: values.week_off_start_day,
        ...(values.password ? { password: values.password } : {}),
      };
      return editing
        ? employeesApi.update(editing.id, payload)
        : employeesApi.create(payload);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
      setDialogOpen(false);
      setEditing(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to save employee"),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: number) => employeesApi.deactivate(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
      setDeactivateTarget(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to deactivate"),
  });

  const resetMutation = useMutation({
    mutationFn: ({ id, password }: { id: number; password: string }) =>
      employeesApi.resetPassword(id, password),
    onSuccess: () => {
      setError(null);
      setResetTarget(null);
      resetForm.reset({ password: "" });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to reset password"),
  });

  const openCreate = () => {
    setEditing(null);
    setError(null);
    setDialogOpen(true);
  };

  const openEdit = (employee: Employee) => {
    setEditing(employee);
    setError(null);
    setDialogOpen(true);
  };

  const onSubmit = form.handleSubmit((values) => {
    setError(null);
    saveMutation.mutate(values);
  });

  const onResetSubmit = resetForm.handleSubmit((values) => {
    if (!resetTarget) return;
    setError(null);
    resetMutation.mutate({ id: resetTarget.id, password: values.password });
  });

  const employees = useMemo(
    () => sortEmployees(employeesQuery.data ?? [], sortKey),
    [employeesQuery.data, sortKey],
  );

  return (
    <div>
      <PageHeader
        title="Employees"
        description="Manage employee records, accounts, and availability."
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => setShowInactive((current) => !current)}
            >
              {showInactive ? "Hide inactive" : "Show inactive"}
            </Button>
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" /> Add employee
            </Button>
          </>
        }
      />

      <ErrorBanner message={error} />

      <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
        <label htmlFor="employee-sort" className="text-xs font-medium text-muted-foreground">
          Sort by
        </label>
        <Select
          id="employee-sort"
          aria-label="Sort employees"
          value={sortKey}
          onChange={(event) => setSortKey(event.target.value as EmployeeSortKey)}
          className="h-8 w-auto min-w-[170px] text-xs"
        >
          {EMPLOYEE_SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b bg-slate-50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th scope="col" className="px-4 py-3 font-medium">Employee</th>
                  <th scope="col" className="px-4 py-3 font-medium">Email</th>
                  <th scope="col" className="px-4 py-3 font-medium">Primary shift</th>
                  <th scope="col" className="px-4 py-3 font-medium">Status</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {employeesQuery.isLoading ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">
                      Loading employees…
                    </td>
                  </tr>
                ) : employees.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">
                      No employees yet. Add your first employee.
                    </td>
                  </tr>
                ) : (
                  employees.map((employee) => (
                    <tr key={employee.id} className="border-b last:border-0">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                            <UserRound className="h-4 w-4" />
                          </span>
                          <div>
                            <p className="font-medium">{employee.full_name}</p>
                            <p className="text-xs text-muted-foreground">{employee.employee_code}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{employee.email}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {employee.default_shift ?? "Auto (balanced)"}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={employee.is_active ? "success" : "muted"}>
                          {employee.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => openEdit(employee)}>
                            <Pencil className="h-3.5 w-3.5" /> Edit
                          </Button>
                          <Button variant="ghost" size="sm" asChild>
                            <Link to={`/admin/employees/${employee.id}`}>Availability</Link>
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              resetForm.reset({ password: "" });
                              setResetTarget(employee);
                            }}
                          >
                            <KeyRound className="h-3.5 w-3.5" /> Reset
                          </Button>
                          {employee.is_active ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => setDeactivateTarget(employee)}
                            >
                              <UserMinus className="h-3.5 w-3.5" /> Deactivate
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit employee" : "Add employee"}</DialogTitle>
            <DialogDescription>
              {editing
                ? "Update the employee record. Leave the password blank to keep the current one."
                : "Create the employee record and login account. The default password is Employee123! if left blank."}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="employee_code">Employee ID</Label>
                <Input id="employee_code" placeholder="EMP018" {...form.register("employee_code")} />
                {form.formState.errors.employee_code ? (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.employee_code.message}
                  </p>
                ) : null}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="full_name">Full name</Label>
                <Input id="full_name" placeholder="Aarav Sharma" {...form.register("full_name")} />
                {form.formState.errors.full_name ? (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.full_name.message}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" placeholder="aarav@example.com" {...form.register("email")} />
              {form.formState.errors.email ? (
                <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
              ) : null}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="default_shift">Primary shift</Label>
              <Select id="default_shift" {...form.register("default_shift")}>
                <option value="">Auto (balanced)</option>
                {workingStatuses.map((status) => (
                  <option key={status.code} value={status.code}>
                    {status.code} — {status.label}
                  </option>
                ))}
              </Select>
              <p className="text-xs text-muted-foreground">
                Employees keep this shift all month. Coverage needs can move them to another shift
                when their shift is over-subscribed.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="week_off_start_day">Week off</Label>
              <Select id="week_off_start_day" {...form.register("week_off_start_day")}>
                {WEEK_OFF_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
              <p className="text-xs text-muted-foreground">
                Two consecutive days off each week. Generation never schedules work on these days.
              </p>
            </div>
            {!editing ? (
              <div className="space-y-1.5">
                <Label htmlFor="password">Initial password (optional)</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="At least 8 characters"
                  {...form.register("password")}
                />
                {form.formState.errors.password ? (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.password.message}
                  </p>
                ) : null}
              </div>
            ) : null}
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? "Saving…" : editing ? "Save changes" : "Add employee"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deactivateTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeactivateTarget(null);
        }}
        title="Deactivate employee"
        description={`Deactivate ${deactivateTarget?.full_name ?? "this employee"}? They will no longer be able to sign in and existing sessions are revoked.`}
        confirmLabel="Deactivate"
        destructive
        pending={deactivateMutation.isPending}
        onConfirm={() => {
          if (deactivateTarget) deactivateMutation.mutate(deactivateTarget.id);
        }}
      />

      <Dialog
        open={resetTarget !== null}
        onOpenChange={(open) => {
          if (!open) setResetTarget(null);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Reset password</DialogTitle>
            <DialogDescription>
              Set a new password for {resetTarget?.full_name ?? "this employee"}. Existing sessions
              will be signed out.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={onResetSubmit} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="reset-password">New password</Label>
              <Input
                id="reset-password"
                type="password"
                autoComplete="new-password"
                {...resetForm.register("password")}
              />
              {resetForm.formState.errors.password ? (
                <p className="text-xs text-destructive">
                  {resetForm.formState.errors.password.message}
                </p>
              ) : null}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setResetTarget(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={resetMutation.isPending}>
                {resetMutation.isPending ? "Saving…" : "Reset password"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
