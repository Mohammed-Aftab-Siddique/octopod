import { ArrowRight, CalendarDays, Search } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { employeesApi } from "@/api/endpoints";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { EmployeeLookup } from "@/lib/types";

export function LookupPage() {
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [result, setResult] = useState<EmployeeLookup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onLookup = async (event: React.FormEvent) => {
    event.preventDefault();
    setResult(null);
    setError(null);
    if (!code.trim()) {
      setError("Enter your employee ID.");
      return;
    }
    setLoading(true);
    try {
      const response = await employeesApi.lookup(code.trim());
      setResult(response);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 404
            ? "No active employee found with that ID."
            : err.message
          : "Lookup failed. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-slate-100 to-slate-50 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <CalendarDays className="h-5 w-5" />
          </span>
          <span className="text-xl font-semibold tracking-tight">Octopod Roster</span>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Find your account</CardTitle>
            <CardDescription>
              Enter your employee ID to confirm your name, then continue to sign in.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ErrorBanner message={error} />
            {result ? (
              <div className="space-y-4">
                <div className="rounded-md border bg-emerald-50 px-4 py-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                    Employee found
                  </p>
                  <p className="mt-1 text-lg font-semibold">{result.full_name}</p>
                  <p className="text-sm text-muted-foreground">{result.employee_code}</p>
                </div>
                <Button
                  className="w-full"
                  onClick={() =>
                    navigate(`/login?identifier=${encodeURIComponent(result.employee_code)}`)
                  }
                >
                  Continue to sign in <ArrowRight className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  className="w-full"
                  onClick={() => {
                    setResult(null);
                    setCode("");
                  }}
                >
                  Look up another ID
                </Button>
              </div>
            ) : (
              <form onSubmit={onLookup} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="employee-code">Employee ID</Label>
                  <Input
                    id="employee-code"
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                    placeholder="EMP001"
                    autoFocus
                  />
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  <Search className="h-4 w-4" />
                  {loading ? "Looking up…" : "Look up employee"}
                </Button>
              </form>
            )}
            <div className="mt-4 flex items-center justify-between text-sm">
              <Link to="/login" className="text-muted-foreground underline-offset-4 hover:underline">
                Back to sign in
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
