import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { User } from "@/lib/types";

const auth = vi.hoisted(() => ({
  value: { user: null as User | null, loading: false },
}));

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => auth.value,
}));

import { RequireAdmin, RequireAuth } from "@/components/Guards";

function renderPrivate(guard: "auth" | "admin") {
  return render(
    <MemoryRouter initialEntries={["/private"]}>
      <Routes>
        <Route element={guard === "auth" ? <RequireAuth /> : <RequireAdmin />}>
          <Route path="/private" element={<div>private page</div>} />
        </Route>
        <Route path="/login" element={<div>login page</div>} />
        <Route path="/" element={<div>home page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("route guards", () => {
  it("redirects unauthenticated users to login", () => {
    auth.value = { user: null, loading: false };
    renderPrivate("auth");
    expect(screen.getByText("login page")).toBeInTheDocument();
  });

  it("shows the loading state while auth is resolving", () => {
    auth.value = { user: null, loading: true };
    renderPrivate("auth");
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("sends non-admins away from admin routes", () => {
    auth.value = {
      user: {
        id: 2,
        email: "employee@example.com",
        role: "employee",
        employee_id: 1,
        full_name: "Employee",
        employee_code: "E001",
      },
      loading: false,
    };
    renderPrivate("admin");
    expect(screen.getByText("home page")).toBeInTheDocument();
  });

  it("allows admins through", () => {
    auth.value = {
      user: {
        id: 1,
        email: "admin@example.com",
        role: "admin",
        employee_id: null,
        full_name: "Administrator",
        employee_code: null,
      },
      loading: false,
    };
    renderPrivate("admin");
    expect(screen.getByText("private page")).toBeInTheDocument();
  });
});
