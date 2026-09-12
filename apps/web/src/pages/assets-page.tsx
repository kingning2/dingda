import { Navigate, useSearchParams } from "react-router-dom";
import { paths } from "@v2/routes/paths";

/** @deprecated 资产页已拆成 /agents 与 /accounts。 */
export function AssetsPage() {
  const [searchParams] = useSearchParams();
  const tab = searchParams.get("tab");
  if (tab === "accounts") {
    return <Navigate to={paths.accounts} replace />;
  }
  return <Navigate to={paths.agents} replace />;
}
