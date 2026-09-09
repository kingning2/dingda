import { Navigate } from "react-router-dom";
import { paths } from "@/routes/paths";

/** @deprecated 使用 /agents */
export function IntegrationsPage() {
  return <Navigate to={paths.agents} replace />;
}
