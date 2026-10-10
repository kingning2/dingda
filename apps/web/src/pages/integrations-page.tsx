import { Navigate } from "react-router-dom";
import { paths } from "@v2/routes/paths";

/** @deprecated 旧「集成」入口（外部 CLI 集成已移除），统一落账号页。 */
export function IntegrationsPage() {
  return <Navigate to={paths.accounts} replace />;
}
