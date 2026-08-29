/**
 * 应用路由：选品产品路径；旧客服 / channel 路径 redirect 到工作台。
 */

import { createBrowserRouter, Navigate } from "react-router";
import { featureRoutePath, listWorkspaceFeatures } from "@feature/workspace-features";

import { AccessGate } from "../app/access-gate";
import { ServiceUnavailablePage } from "../app/pages/service-unavailable-page";
import { AppShell } from "../app/shell";

function WorkspacePathMarker() {
  return null;
}

function workspaceRoute(path: string) {
  return { path, element: <WorkspacePathMarker /> };
}

const PRODUCT_ROUTE_PATHS = [
  "dashboard",
  "discovery",
  "discovery/high-profit",
  "discovery/hot",
  "discovery/blue-ocean",
  "discovery/new",
  "discovery/start",
  "products",
  "products/:productId",
  "products/:productId/supply",
  "products/:productId/demand",
  "products/:productId/matches",
  "products/:productId/profit",
  "products/:productId/history",
  "profit",
  "profit/calculator",
  "profit/templates",
  "monitoring",
  "monitoring/subscriptions",
  "monitoring/alerts",
  "monitoring/rules",
  "tasks",
  "tasks/:taskId",
  "settings",
  "settings/general",
  "settings/accounts",
  "settings/collection",
  "settings/profit",
  "settings/ai",
  "settings/subscription",
];

export const appRouter = createBrowserRouter([
  { path: "/503", element: <ServiceUnavailablePage /> },
  {
    path: "/",
    element: (
      <AccessGate>
        <AppShell />
      </AccessGate>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      ...PRODUCT_ROUTE_PATHS.map((path) => workspaceRoute(path)),
      ...listWorkspaceFeatures().map((feature) =>
        workspaceRoute(featureRoutePath(feature)),
      ),
      { path: "features/discovery", element: <Navigate to="/discovery" replace /> },
      { path: "features/ai", element: <Navigate to="/settings/ai" replace /> },
      { path: "features/chat", element: <Navigate to="/dashboard" replace /> },
      { path: "features/knowledge", element: <Navigate to="/dashboard" replace /> },
      { path: "features/channel", element: <Navigate to="/dashboard" replace /> },
      { path: "features/channel/*", element: <Navigate to="/dashboard" replace /> },
    ],
  },
]);
