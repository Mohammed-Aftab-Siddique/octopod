import { CalendarDays, LogOut } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/AuthProvider";
import { cn } from "@/lib/utils";

const employeeLinks = [{ to: "/", label: "My roster", end: true }];
const adminLinks = [
  { to: "/admin/employees", label: "Employees" },
  { to: "/admin/rosters", label: "Rosters" },
  { to: "/admin/settings", label: "Settings" },
];

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const links = user?.role === "admin" ? [...employeeLinks, ...adminLinks] : employeeLinks;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-card/95 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-[1700px] items-center justify-between gap-4 px-4">
          <button
            className="flex items-center gap-2 text-left"
            onClick={() => navigate("/")}
            aria-label="Octopod home"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <CalendarDays className="h-4 w-4" />
            </span>
            <span className="text-base font-semibold tracking-tight">Octopod</span>
          </button>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium leading-tight">
                {user?.full_name ?? user?.email}
              </p>
              <p className="text-xs text-muted-foreground">
                {user?.employee_code ? `${user.employee_code} · ` : ""}
                {user?.role === "admin" ? "Administrator" : "Employee"}
              </p>
            </div>
            <Badge variant={user?.role === "admin" ? "default" : "secondary"} className="hidden sm:inline-flex">
              {user?.role}
            </Badge>
            <Button variant="ghost" size="icon" onClick={() => void logout()} aria-label="Log out">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <nav className="mx-auto flex w-full max-w-[1700px] gap-1 overflow-x-auto px-3 pb-2">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                cn(
                  "whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  isActive && "bg-muted text-foreground",
                )
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto w-full max-w-[1700px] flex-1 px-3 py-5 sm:px-4">
        <Outlet />
      </main>
      <footer className="border-t py-4 text-center text-xs text-muted-foreground">
        Octopod · monthly shift roster
      </footer>
    </div>
  );
}
