import { Navigate } from "react-router-dom";
import { paths } from "@v2/routes/paths";

/** @deprecated 旧「资产」入口，现已归入 /accounts。 */
export function AssetsPage() {
  return <Navigate to={paths.accounts} replace />;
}
