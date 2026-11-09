import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarDays } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { ErrorBanner } from "@/components/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError } from "@/api/client";

const schema = z.object({
  identifier: z.string().min(1, "Enter your email or employee ID"),
  password: z.string().min(1, "Enter your password"),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      identifier: params.get("identifier") ?? "",
      password: "",
    },
  });

  if (user) {
    return <Navigate to="/" replace />;
  }

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await login(values.identifier.trim(), values.password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== "/login" ? from : "/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to sign in. Please try again.");
    }
  });

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
            <CardTitle>Sign in</CardTitle>
            <CardDescription>
              Use your email or employee ID. New here?{" "}
              <Link to="/lookup" className="font-medium text-primary underline-offset-4 hover:underline">
                Look up your ID
              </Link>
              .
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ErrorBanner message={error} />
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="identifier">Email or employee ID</Label>
                <Input
                  id="identifier"
                  autoComplete="username"
                  placeholder="you@example.com or EMP001"
                  {...form.register("identifier")}
                />
                {form.formState.errors.identifier ? (
                  <p className="text-xs text-destructive">{form.formState.errors.identifier.message}</p>
                ) : null}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  {...form.register("password")}
                />
                {form.formState.errors.password ? (
                  <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>
                ) : null}
              </div>
              <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? "Signing in…" : "Sign in"}
              </Button>
            </form>
            <p className="mt-4 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
              Demo accounts: <span className="font-medium text-foreground">admin@example.com</span> /{" "}
              <span className="font-medium text-foreground">Admin123!</span> ·{" "}
              <span className="font-medium text-foreground">EMP001</span> /{" "}
              <span className="font-medium text-foreground">Employee123!</span>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
