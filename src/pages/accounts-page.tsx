import { Navigate } from "react-router-dom";

/** @deprecated 使用 /assets?tab=accounts */
export function AccountsPage() {
  return <Navigate to="/assets?tab=accounts" replace />;
}
