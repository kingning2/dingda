import { Outlet } from "react-router-dom";

import { AppShell } from "@v2/ui-layout/app-shell";

export function AppLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
