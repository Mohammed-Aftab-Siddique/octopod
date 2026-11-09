import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { CalendarPlus, ExternalLink } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { rostersApi } from "@/api/endpoints";
import { ErrorBanner } from "@/components/ErrorBanner";
import { MonthPicker } from "@/components/MonthPicker";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { currentMonth, monthLabel, statusBadgeClass } from "@/lib/utils";

export function AdminRostersPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [month, setMonth] = useState(currentMonth);
  const [error, setError] = useState<string | null>(null);

  const rostersQuery = useQuery({
    queryKey: ["rosters", month.year, month.month],
    queryFn: () => rostersApi.list(month.year, month.month),
  });

  const createMutation = useMutation({
    mutationFn: () => rostersApi.create(month.year, month.month),
    onSuccess: (grid) => {
      void queryClient.invalidateQueries({ queryKey: ["rosters"] });
      navigate(`/admin/rosters/${grid.id}`);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to create roster"),
  });

  const rosters = rostersQuery.data ?? [];

  return (
    <div>
      <PageHeader
        title="Rosters"
        description="Create, generate, review, and publish monthly rosters."
        actions={
          <>
            <MonthPicker year={month.year} month={month.month} onChange={setMonth} />
            <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              <CalendarPlus className="h-4 w-4" />
              {createMutation.isPending ? "Creating…" : "New draft"}
            </Button>
          </>
        }
      />

      <ErrorBanner message={error} />

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b bg-slate-50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Month</th>
                  <th className="px-4 py-3 font-medium">Version</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium">Published</th>
                  <th className="px-4 py-3 text-right font-medium">Open</th>
                </tr>
              </thead>
              <tbody>
                {rostersQuery.isLoading ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                      Loading rosters…
                    </td>
                  </tr>
                ) : rosters.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                      No roster for {monthLabel(month.year, month.month)} yet. Create a new draft
                      to begin.
                    </td>
                  </tr>
                ) : (
                  rosters.map((roster) => (
                    <tr key={roster.id} className="border-b last:border-0">
                      <td className="px-4 py-3 font-medium">
                        {monthLabel(roster.year, roster.month)}
                      </td>
                      <td className="px-4 py-3">v{roster.version}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${statusBadgeClass(
                            roster.status,
                          )}`}
                        >
                          {roster.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {format(new Date(roster.created_at), "d MMM yyyy, HH:mm")}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {roster.published_at
                          ? format(new Date(roster.published_at), "d MMM yyyy, HH:mm")
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`/admin/rosters/${roster.id}`)}
                        >
                          <ExternalLink className="h-3.5 w-3.5" /> Open
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <p className="mt-3 text-xs text-muted-foreground">
        Publishing a draft archives the previously published version for that month. Employees only
        ever see the currently published roster.
      </p>
    </div>
  );
}
