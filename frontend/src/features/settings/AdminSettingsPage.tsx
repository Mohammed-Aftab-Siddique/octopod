import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { referenceApi } from "@/api/endpoints";
import { ErrorBanner } from "@/components/ErrorBanner";
import { MonthPicker } from "@/components/MonthPicker";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RosterLegend } from "@/components/roster/RosterLegend";
import { firstDayOfMonthIso, formatDateOnly } from "@/lib/dates";
import { currentMonth } from "@/lib/utils";

const holidaySchema = z.object({
  date: z.string().min(1, "Choose a date"),
  label: z.string().trim().min(1, "Enter a holiday label").max(120),
});

type HolidayForm = z.infer<typeof holidaySchema>;

function monthRange(year: number, month: number) {
  const lastDay = new Date(year, month, 0).getDate();
  return {
    first: firstDayOfMonthIso(year, month),
    last: `${year}-${String(month).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`,
  };
}

export function AdminSettingsPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [month, setMonth] = useState(currentMonth);

  const statusesQuery = useQuery({
    queryKey: ["shift-statuses"],
    queryFn: () => referenceApi.listStatuses(),
  });

  const workingStatuses = useMemo(
    () =>
      (statusesQuery.data ?? []).filter(
        (status) => status.is_working && status.code !== "H",
      ),
    [statusesQuery.data],
  );

  const requirementsQuery = useQuery({
    queryKey: ["staffing-requirements"],
    queryFn: () => referenceApi.listRequirements(),
  });

  const range = monthRange(month.year, month.month);
  const holidayForm = useForm<HolidayForm>({
    resolver: zodResolver(holidaySchema),
    defaultValues: { date: range.first, label: "" },
  });

  useEffect(() => {
    if (!requirementsQuery.data) return;
    const next: Record<string, number> = {};
    for (const requirement of requirementsQuery.data) {
      next[requirement.status_code] = requirement.required_count;
    }
    setCounts(next);
  }, [requirementsQuery.data]);

  const saveRequirements = useMutation({
    mutationFn: () =>
      referenceApi.saveRequirements(
        workingStatuses.map((status) => ({
          status_code: status.code,
          required_count: counts[status.code] ?? 0,
        })),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staffing-requirements"] });
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Unable to save requirements"),
  });

  const holidaysQuery = useQuery({
    queryKey: ["holidays", month.year, month.month],
    queryFn: () => referenceApi.listHolidays(month.year, month.month),
  });

  const addHoliday = useMutation({
    mutationFn: (values: HolidayForm) => referenceApi.createHoliday(values.date, values.label),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["holidays", month.year, month.month] });
      holidayForm.setValue("label", "");
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to add holiday"),
  });

  const deleteHoliday = useMutation({
    mutationFn: (holidayId: number) => referenceApi.deleteHoliday(holidayId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["holidays"] }),
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to remove holiday"),
  });

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Configure staffing coverage, holidays, and review the status legend."
      />

      <ErrorBanner message={error} />

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader className="flex-row items-start justify-between space-y-0">
            <div>
              <CardTitle>Staffing requirements</CardTitle>
              <CardDescription>
                Number of people who belong to each working shift for the whole month. The same
                headcount applies every day, so employees on their week-off still count towards
                their shift.
              </CardDescription>
            </div>
            <Button
              onClick={() => saveRequirements.mutate()}
              disabled={saveRequirements.isPending || workingStatuses.length === 0}
            >
              <Save className="h-4 w-4" />
              {saveRequirements.isPending ? "Saving…" : "Save"}
            </Button>
          </CardHeader>
          <CardContent className="space-y-3 p-4">
            {workingStatuses.map((status) => (
              <div key={status.code} className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <span
                    className="inline-block h-3 w-3 rounded-sm"
                    style={{ backgroundColor: status.color }}
                  />
                  {status.label}
                  <span className="text-xs text-muted-foreground">({status.code})</span>
                </div>
                <Input
                  type="number"
                  min={0}
                  max={10000}
                  className="h-8 w-20 text-center"
                  value={counts[status.code] ?? 0}
                  onChange={(event) =>
                    setCounts((current) => ({
                      ...current,
                      [status.code]: Math.max(0, Number(event.target.value) || 0),
                    }))
                  }
                  aria-label={`${status.label} headcount`}
                />
              </div>
            ))}
            {workingStatuses.length === 0 ? (
              <p className="text-sm text-muted-foreground">No working shifts configured.</p>
            ) : null}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>Holidays</CardTitle>
                <CardDescription>Holidays are highlighted with the H status.</CardDescription>
              </div>
              <MonthPicker
                year={month.year}
                month={month.month}
                onChange={(next) => {
                  setMonth(next);
                  holidayForm.setValue("date", firstDayOfMonthIso(next.year, next.month));
                }}
              />
            </CardHeader>
            <CardContent className="space-y-4">
              <form
                className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]"
                onSubmit={holidayForm.handleSubmit((values) => {
                  setError(null);
                  addHoliday.mutate(values);
                })}
              >
                <div className="space-y-1">
                  <Label htmlFor="holiday-date" className="text-xs">
                    Date
                  </Label>
                  <Input
                    id="holiday-date"
                    type="date"
                    min={range.first}
                    max={range.last}
                    {...holidayForm.register("date")}
                  />
                  {holidayForm.formState.errors.date ? (
                    <p className="text-xs text-destructive">
                      {holidayForm.formState.errors.date.message}
                    </p>
                  ) : null}
                </div>
                <div className="space-y-1">
                  <Label htmlFor="holiday-label" className="text-xs">
                    Label
                  </Label>
                  <Input
                    id="holiday-label"
                    placeholder="Company holiday"
                    {...holidayForm.register("label")}
                  />
                  {holidayForm.formState.errors.label ? (
                    <p className="text-xs text-destructive">
                      {holidayForm.formState.errors.label.message}
                    </p>
                  ) : null}
                </div>
                <Button type="submit" className="self-end" disabled={addHoliday.isPending}>
                  <Plus className="h-4 w-4" /> Add
                </Button>
              </form>

              <div className="space-y-1">
                {holidaysQuery.data?.length ? (
                  holidaysQuery.data.map((holiday) => (
                    <div
                      key={holiday.id}
                      className="flex items-center justify-between rounded-md border bg-violet-50 px-3 py-2 text-sm"
                    >
                      <div>
                        <span className="font-medium">{formatDateOnly(holiday.date)}</span>
                        <span className="ml-2 text-muted-foreground">{holiday.label}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Delete holiday"
                        onClick={() => deleteHoliday.mutate(holiday.id)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  ))
                ) : (
                  <p className="py-2 text-sm text-muted-foreground">
                    No holidays configured for this month.
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Status legend</CardTitle>
              <CardDescription>
                Codes and colours used across the roster, including the holiday code.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {statusesQuery.data ? <RosterLegend statuses={statusesQuery.data} /> : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
