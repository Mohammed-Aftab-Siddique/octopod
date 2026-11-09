import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { RequireAdmin, RequireAuth } from "@/components/Guards";
import { LoginPage } from "@/features/auth/LoginPage";
import { LookupPage } from "@/features/auth/LookupPage";
import { AdminEmployeeDetailPage } from "@/features/employees/AdminEmployeeDetailPage";
import { AdminEmployeesPage } from "@/features/employees/AdminEmployeesPage";
import { AdminRosterPage } from "@/features/roster/AdminRosterPage";
import { AdminRostersPage } from "@/features/roster/AdminRostersPage";
import { MyRosterPage } from "@/features/roster/MyRosterPage";
import { AdminSettingsPage } from "@/features/settings/AdminSettingsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/lookup" element={<LookupPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<MyRosterPage />} />
          <Route element={<RequireAdmin />}>
            <Route path="admin/employees" element={<AdminEmployeesPage />} />
            <Route path="admin/employees/:id" element={<AdminEmployeeDetailPage />} />
            <Route path="admin/rosters" element={<AdminRostersPage />} />
            <Route path="admin/rosters/:id" element={<AdminRosterPage />} />
            <Route path="admin/settings" element={<AdminSettingsPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
