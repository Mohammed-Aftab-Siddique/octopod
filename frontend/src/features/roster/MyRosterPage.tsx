import { useQuery } from "@tanstack/react-query";
import { CalendarOff, Download, Users } from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/api/client";
import { rostersApi } from "@/api/endpoints";
import { ErrorBanner } from "@/components/ErrorBanner";
import { MonthPicker } from "@/components/MonthPicker";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RosterGrid } from "@/components/roster/RosterGrid";
import { RosterLegend } from "@/components/roster/RosterLegend";
import { useAuth } from "@/features/auth/AuthProvider";
import { cn, currentMonth, monthLabel } from "@/lib/utils";

type ViewMode = "mine" | "team";

export function MyRosterPage() {
  const { user } = useAuth();
  const [month, setMonth] = useState(currentMonth);
  const [view, setView] = useState<ViewMode>(() =>
    user?.role === "admin" ? "team" : "mine",
  );
  const [exportError, setExportError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["my-roster", month.year, month.month],
    queryFn: () => rostersApi.myRoster(month.year, month.month),
    retry: false,
  });

  const downloadExport = async () => {
    if (!query.data) return;
    setExportError(null);
    try {
      await rostersApi.downloadExport(query.data.id, query.data);
    } catch (error) {
      setExportError(error instanceof ApiError ? error.message : "Unable to export roster.");
    }
  };

  const notFound = query.error instanceof ApiError && query.error.status === 404;

  return (
    <div>
      <PageHeader
        title="My roster"
        description="Your published shift roster. Your own row is highlighted by default."
        actions={
          <>
            <MonthPicker year={month.year} month={month.month} onChange={setMonth} />
            <Button variant="outline" onClick={() => void downloadExport()} disabled={!query.data}>
              <Download className="h-4 w-4" /> Export PNG
            </Button>
          </>
        }
      />

      <ErrorBanner message={exportError} />

      {query.isLoading ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Loading roster…
          </CardContent>
        </Card>
      ) : notFound ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-14 text-center">
            <CalendarOff className="h-8 w-8 text-muted-foreground" />
            <p className="font-medium">No published roster for {monthLabel(month.year, month.month)}</p>
            <p className="text-sm text-muted-foreground">
              Your administrator has not published a roster for this month yet.
            </p>
          </CardContent>
        </Card>
      ) : query.isError ? (
        <ErrorBanner message={(query.error as Error).message} />
      ) : query.data ? (
        <>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="inline-flex rounded-md border bg-card p-1">
              <button
                type="button"
                aria-pressed={view === "mine"}
                onClick={() => setView("mine")}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded px-3 py-1 text-sm font-medium",
                  view === "mine" ? "bg-primary text-primary-foreground" : "text-muted-foreground",
                )}
              >
                <Users className="h-3.5 w-3.5" /> My row
              </button>
              <button
                type="button"
                aria-pressed={view === "team"}
                onClick={() => setView("team")}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded px-3 py-1 text-sm font-medium",
                  view === "team" ? "bg-primary text-primary-foreground" : "text-muted-foreground",
                )}
              >
                <Users className="h-3.5 w-3.5" /> Full team
              </button>
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Badge variant="success">Published</Badge>
              <span>
                {monthLabel(month.year, month.month)} · version {query.data.version}
              </span>
            </div>
          </div>

          {view === "mine" && !user?.employee_id ? (
            <Card>
              <CardHeader>
                <CardTitle>No employee profile linked</CardTitle>
                <CardDescription>
                  Your account is not linked to an employee record. Use the full team view.
                </CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <RosterGrid
              grid={query.data}
              employeeFilterId={view === "mine" ? user?.employee_id : null}
              highlightEmployeeId={user?.employee_id}
            />
          )}
          <RosterLegend statuses={query.data.statuses} />
        </>
      ) : null}
    </div>
  );
}
