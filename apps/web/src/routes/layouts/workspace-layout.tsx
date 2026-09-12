import { Outlet } from "react-router-dom";

import { WorkspaceShell } from "@v2/ui-layout/workspace-shell";

export function WorkspaceLayout() {
  return (
    <WorkspaceShell>
      <Outlet />
    </WorkspaceShell>
  );
}
