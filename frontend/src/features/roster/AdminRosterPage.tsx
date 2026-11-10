import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { ArrowLeft, CheckCircle2, Download, Sparkles, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { rostersApi } from "@/api/endpoints";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { RosterGrid } from "@/components/roster/RosterGrid";
import { RosterLegend } from "@/components/roster/RosterLegend";
import { StatusPicker } from "@/components/roster/StatusPicker";
import { formatDateOnly } from "@/lib/dates";
import type {
  GenerationResult,
  RosterDay,
  RosterEmployee,
  RosterGrid as Grid,
} from "@/lib/types";
import { monthLabel, statusBadgeClass } from "@/lib/utils";

interface PickerState {
  employee: RosterEmployee;
  day: RosterDay;
  currentCode?: string;
}

export function AdminRosterPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const rosterId = Number(id);
  const queryClient = useQueryClient();
  const queryKey = ["roster", rosterId];
  const [error, setError] = useState<string | null>(null);
  const [picker, setPicker] = useState<PickerState | null>(null);
  const [generation, setGeneration] = useState<GenerationResult | null>(null);
  const [confirmAction, setConfirmAction] = useState<"generate" | "publish" | "delete" | null>(
    null,
  );

  const rosterQuery = useQuery({
    queryKey,
    queryFn: () => rostersApi.get(rosterId),
    enabled: Number.isFinite(rosterId),
  });

  const assignmentMutation = useMutation({
    mutationFn: (input: { employeeId: number; date: string; statusCode: string }) =>
      rostersApi.patchAssignments(rosterId, [
        {
          employee_id: input.employeeId,
          date: input.date,
          status_code: input.statusCode,
        },
      ]),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<Grid>(queryKey);
      queryClient.setQueryData<Grid>(queryKey, (current) => {
        if (!current) return current;
        const remaining = current.assignments.filter(
          (assignment) =>
            !(assignment.employee_id === input.employeeId && assignment.date === input.date),
        );
        return {
          ...current,
          assignments: [
            ...remaining,
            {
              employee_id: input.employeeId,
              date: input.date,
              status_code: input.statusCode,
            },
          ],
        };
      });
      return { previous };
    },
    onError: (err, _input, context) => {
      if (context?.previous) queryClient.setQueryData(queryKey, context.previous);
      setError(err instanceof ApiError ? err.message : "Unable to save the assignment");
    },
    onSuccess: (grid) => {
      queryClient.setQueryData(queryKey, grid);
      setError(null);
    },
    onSettled: () => void queryClient.invalidateQueries({ queryKey }),
  });

  const generateMutation = useMutation({
    mutationFn: () => rostersApi.generate(rosterId),
    onSuccess: (result) => {
      queryClient.setQueryData(queryKey, result.roster);
      setGeneration(result);
      setConfirmAction(null);
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to generate roster"),
  });

  const publishMutation = useMutation({
    mutationFn: () => rostersApi.publish(rosterId),
    onSuccess: (grid) => {
      queryClient.setQueryData(queryKey, grid);
      setGeneration(null);
      setConfirmAction(null);
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to publish roster"),
  });

  const deleteMutation = useMutation({
    mutationFn: () => rostersApi.delete(rosterId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["rosters"] });
      queryClient.removeQueries({ queryKey });
      setConfirmAction(null);
      navigate("/admin/rosters");
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to delete roster"),
  });

  const downloadExport = async () => {
    const current = rosterQuery.data;
    if (!current) return;
    setError(null);
    try {
      await rostersApi.downloadExport(current.id, current);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to export roster");
    }
  };

  const grid = rosterQuery.data;
  const isDraft = grid?.status === "draft";

  if (rosterQuery.isLoading) {
    return <div className="py-12 text-center text-sm text-muted-foreground">Loading roster…</div>;
  }
  if (rosterQuery.isError || !grid) {
    return <ErrorBanner message={(rosterQuery.error as Error)?.message ?? "Roster not found"} />;
  }

  return (
    <div>
      <PageHeader
        title={`${monthLabel(grid.year, grid.month)} roster`}
        description={`Version ${grid.version} · last updated ${format(
          new Date(grid.updated_at),
          "d MMM yyyy, HH:mm",
        )}`}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/admin/rosters">
                <ArrowLeft className="h-4 w-4" /> Back
              </Link>
            </Button>
            <Button variant="outline" onClick={() => void downloadExport()}>
              <Download className="h-4 w-4" /> Export PNG
            </Button>
            {isDraft ? (
              <>
                <Button
                  variant="secondary"
                  onClick={() => {
                    if (grid.assignments.length === 0) {
                      generateMutation.mutate();
                    } else {
                      setConfirmAction("generate");
                    }
                  }}
                  disabled={generateMutation.isPending}
                >
                  <Sparkles className="h-4 w-4" />
                  {generateMutation.isPending ? "Generating…" : "Generate"}
                </Button>
                <Button
                  onClick={() => setConfirmAction("publish")}
                  disabled={publishMutation.isPending || assignmentMutation.isPending}
                >
                  <Upload className="h-4 w-4" />
                  {publishMutation.isPending ? "Publishing…" : "Publish"}
                </Button>
              </>
            ) : null}
            <Button
              variant="destructive"
              onClick={() => setConfirmAction("delete")}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="h-4 w-4" />
              {deleteMutation.isPending ? "Deleting…" : "Delete"}
            </Button>
          </>
        }
      />

      <ErrorBanner message={error} />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${statusBadgeClass(
            grid.status,
          )}`}
        >
          {grid.status}
        </span>
        <Badge variant="secondary">{grid.employees.length} employees</Badge>
        <Badge variant="secondary">{grid.days.length} days</Badge>
        <Badge variant="secondary">{grid.assignments.length} assignments</Badge>
        {assignmentMutation.isPending ? (
          <span className="text-xs text-muted-foreground">Saving…</span>
        ) : null}
      </div>

      {isDraft ? (
        <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          This is a draft. Employees cannot see it until you publish. Click any cell to change a
          status — changes save automatically.
        </div>
      ) : grid.status === "published" ? (
        <div className="mb-3 flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          <CheckCircle2 className="h-4 w-4" /> Published
          {grid.published_at
            ? ` on ${format(new Date(grid.published_at), "d MMM yyyy, HH:mm")}`
            : ""}
          . This version is read-only; create a new draft to make changes.
        </div>
      ) : (
        <div className="mb-3 rounded-md border bg-muted px-3 py-2 text-sm text-muted-foreground">
          This version has been archived and replaced by a newer published roster.
        </div>
      )}

      {generation ? (
        <Card className="mb-3 border-blue-200 bg-blue-50/50">
          <CardContent className="space-y-2 p-4 text-sm">
            <div className="flex items-start justify-between gap-3">
              <p className="font-medium text-blue-950">
                Roster generated. Review the draft before publishing.
              </p>
              <Button variant="ghost" size="sm" onClick={() => setGeneration(null)}>
                Dismiss
              </Button>
            </div>
            {generation.shortages.length > 0 ? (
              <div>
                <p className="font-medium text-red-800">
                  {generation.shortages.length} staffing shortage
                  {generation.shortages.length === 1 ? "" : "s"} detected
                </p>
                <ul className="mt-1 max-h-32 overflow-y-auto text-xs text-red-700">
                  {generation.shortages.slice(0, 20).map((shortage) => (
                    <li key={`${shortage.date}-${shortage.status_code}`}>
                      {formatDateOnly(shortage.date, "d MMM")} ·{" "}
                      {shortage.status_code}: {shortage.assigned}/{shortage.required} assigned
                    </li>
                  ))}
                </ul>
                {generation.shortages.length > 20 ? (
                  <p className="mt-1 text-xs text-red-700">
                    …and {generation.shortages.length - 20} more.
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="text-emerald-800">All configured staffing requirements were met.</p>
            )}
            {generation.warnings.map((warning) => (
              <p key={warning} className="text-xs text-blue-900">
                {warning}
              </p>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <RosterGrid
        grid={grid}
        editable={isDraft}
        onEdit={(employee, day, currentCode) => setPicker({ employee, day, currentCode })}
      />
      <RosterLegend statuses={grid.statuses} />

      {picker ? (
        <StatusPicker
          open
          onOpenChange={(open) => {
            if (!open) setPicker(null);
          }}
          employeeName={picker.employee.full_name}
          dateLabel={formatDateOnly(picker.day.date)}
          statuses={grid.statuses}
          currentCode={picker.currentCode}
          onSelect={(statusCode) => {
            assignmentMutation.mutate({
              employeeId: picker.employee.id,
              date: picker.day.date,
              statusCode,
            });
            setPicker(null);
          }}
        />
      ) : null}

      <ConfirmDialog
        open={confirmAction !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmAction(null);
        }}
        title={
          confirmAction === "publish"
            ? "Publish roster"
            : confirmAction === "delete"
              ? "Delete roster"
              : "Regenerate roster"
        }
        description={
          confirmAction === "publish"
            ? "Publish this roster? Employees will see it immediately and the previously published version is archived."
            : confirmAction === "delete"
              ? "Delete this roster permanently? Its assignments and generation history will be removed. This cannot be undone."
              : "Generate a new roster? This replaces the current draft assignments and keeps the roster unpublished."
        }
        confirmLabel={
          confirmAction === "publish" ? "Publish" : confirmAction === "delete" ? "Delete" : "Generate"
        }
        destructive={confirmAction === "publish" || confirmAction === "delete"}
        pending={generateMutation.isPending || publishMutation.isPending || deleteMutation.isPending}
        onConfirm={() => {
          if (confirmAction === "publish") {
            publishMutation.mutate();
          } else if (confirmAction === "delete") {
            deleteMutation.mutate();
          } else if (confirmAction === "generate") {
            generateMutation.mutate();
          }
        }}
      />
    </div>
  );
}
