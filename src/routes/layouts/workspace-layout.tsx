import { Outlet } from "react-router-dom";

import { WorkspaceShell } from "@/components/layout/workspace-shell";

export function WorkspaceLayout() {
  return (
    <WorkspaceShell>
      <Outlet />
    </WorkspaceShell>
  );
}
