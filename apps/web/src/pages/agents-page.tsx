import { AgentRuntimesPanel } from "@v2/ui-agent";
import { supportsExternalAgents } from "@v2/runtime/capabilities";
import { Navigate } from "react-router-dom";
import { paths } from "@v2/routes/paths";

/** 外部 CLI Agent 配置页（仅桌面）。 */
export function AgentsPage() {
  if (!supportsExternalAgents()) {
    return <Navigate to={paths.accounts} replace />;
  }

  return (
    <section>
      <AgentRuntimesPanel />
    </section>
  );
}
