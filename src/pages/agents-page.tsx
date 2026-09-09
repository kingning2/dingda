import { AgentRuntimesPanel } from "@/components/agent";
import { supportsExternalAgents } from "@/lib/capabilities";
import { Navigate } from "react-router-dom";
import { paths } from "@/routes/paths";

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
