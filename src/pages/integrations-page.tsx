import { Navigate } from "react-router-dom";

/** @deprecated 使用 /assets */
export function IntegrationsPage() {
  return <Navigate to="/assets" replace />;
}
