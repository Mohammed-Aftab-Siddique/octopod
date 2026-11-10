import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addMonths, format, startOfMonth } from "date-fns";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { employeesApi } from "@/api/endpoints";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { availabilitySchema, type AvailabilityForm } from "@/features/employees/availabilitySchema";
import { formatDateOnly } from "@/lib/dates";
import type { AvailabilityKind } from "@/lib/types";
import { todayIso } from "@/lib/utils";

const KIND_LABELS: Record<AvailabilityKind, string> = {
  leave: "Leave",
  comp_off: "Compensatory off",
  week_off: "Week-off",
  unavailable: "Unavailable",
};

const KIND_CLASSES: Record<AvailabilityKind, string> = {
  leave: "bg-red-100 text-red-800",
  comp_off: "bg-orange-100 text-orange-800",
  week_off: "bg-slate-200 text-slate-700",
  unavailable: "bg-amber-100 text-amber-800",
};

export function AdminEmployeeDetailPage() {
  const { id } = useParams();
  const employeeId = Number(id);
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const form = useForm<AvailabilityForm>({
    resolver: zodResolver(availabilitySchema),
    defaultValues: {
      start_date: todayIso(),
      end_date: todayIso(),
      kind: "leave",
      note: "",
    },
  });

  const employeeQuery = useQuery({
    queryKey: ["employee", employeeId],
    queryFn: () => employeesApi.get(employeeId),
    enabled: Number.isFinite(employeeId),
  });

  const from = format(startOfMonth(addMonths(new Date(), -1)), "yyyy-MM-dd");
  const to = format(startOfMonth(addMonths(new Date(), 6)), "yyyy-MM-dd");

  const availabilityQuery = useQuery({
    queryKey: ["availability", employeeId, from, to],
    queryFn: () => employeesApi.listAvailability(employeeId, from, to),
    enabled: Number.isFinite(employeeId),
  });

  const addMutation = useMutation({
    mutationFn: (values: AvailabilityForm) =>
      employeesApi.addAvailability(employeeId, {
        start_date: values.start_date,
        end_date: values.end_date,
        kind: values.kind,
        note: values.note?.trim() || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["availability", employeeId] });
      setError(null);
      form.setValue("note", "");
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to save availability"),
  });

  const deleteMutation = useMutation({
    mutationFn: (availabilityId: number) =>
      employeesApi.deleteAvailability(employeeId, availabilityId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["availability", employeeId] }),
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to remove entry"),
  });

  const onSubmit = form.handleSubmit((values) => {
    setError(null);
    addMutation.mutate(values);
  });

  const employee = employeeQuery.data;

  return (
    <div>
      <PageHeader
        title={employee?.full_name ?? "Employee"}
        description={
          employee
            ? `${employee.employee_code} · ${employee.email} · ${employee.default_shift ?? "auto"} shift · ${employee.weekly_off_days} off/week · rotation offset ${employee.rotation_offset}`
            : "Loading employee details…"
        }
        actions={
          <Button variant="outline" asChild>
            <Link to="/admin/employees">
              <ArrowLeft className="h-4 w-4" /> Back to employees
            </Link>
          </Button>
        }
      />

      <ErrorBanner message={error} />

      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Add availability</CardTitle>
            <CardDescription>
              Leave is pre-approved. Record ranges for any dates in the month, including past dates.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={onSubmit}>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1.5">
                  <Label htmlFor="start_date">From</Label>
                  <Input
                    id="start_date"
                    type="date"
                    {...form.register("start_date", {
                      onChange: (event) => {
                        const value = event.target.value;
                        if (form.getValues("end_date") < value) {
                          form.setValue("end_date", value, { shouldValidate: true });
                        }
                      },
                    })}
                  />
                  {form.formState.errors.start_date ? (
                    <p className="text-xs text-destructive">
                      {form.formState.errors.start_date.message}
                    </p>
                  ) : null}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="end_date">To</Label>
                  <Input
                    id="end_date"
                    type="date"
                    min={form.watch("start_date")}
                    {...form.register("end_date")}
                  />
                  {form.formState.errors.end_date ? (
                    <p className="text-xs text-destructive">
                      {form.formState.errors.end_date.message}
                    </p>
                  ) : null}
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="kind">Type</Label>
                <Select id="kind" {...form.register("kind")}>
                  {(Object.keys(KIND_LABELS) as AvailabilityKind[]).map((kind) => (
                    <option key={kind} value={kind}>
                      {KIND_LABELS[kind]}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="note">Note (optional)</Label>
                <Input id="note" placeholder="Approved leave" {...form.register("note")} />
                {form.formState.errors.note ? (
                  <p className="text-xs text-destructive">{form.formState.errors.note.message}</p>
                ) : null}
              </div>
              <Button type="submit" className="w-full" disabled={addMutation.isPending}>
                <Plus className="h-4 w-4" /> {addMutation.isPending ? "Adding…" : "Add availability"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>Upcoming availability</CardTitle>
              <CardDescription>
                {formatDateOnly(from, "d MMM yyyy")} – {formatDateOnly(to, "d MMM yyyy")}
              </CardDescription>
            </div>
            {availabilityQuery.data ? (
              <Badge variant="secondary">{availabilityQuery.data.length} entries</Badge>
            ) : null}
          </CardHeader>
          <CardContent className="p-0">
            <div className="max-h-[520px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Date</th>
                    <th className="px-4 py-2 font-medium">Type</th>
                    <th className="px-4 py-2 font-medium">Note</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {availabilityQuery.isLoading ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                        Loading…
                      </td>
                    </tr>
                  ) : availabilityQuery.data?.length ? (
                    availabilityQuery.data.map((entry) => (
                      <tr key={entry.id} className="border-b last:border-0">
                        <td className="px-4 py-2 font-medium">
                          {formatDateOnly(entry.date)}
                        </td>
                        <td className="px-4 py-2">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${KIND_CLASSES[entry.kind]}`}
                          >
                            {KIND_LABELS[entry.kind]}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-muted-foreground">{entry.note ?? "—"}</td>
                        <td className="px-4 py-2 text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Remove availability"
                            onClick={() => deleteMutation.mutate(entry.id)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                        No availability recorded in this range.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
