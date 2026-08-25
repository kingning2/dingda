/**
 * 应用路由：壳层常驻；具体 Feature 由 WorkspaceOutlet 按标签懒加载。
 *
 * 渠道相关路由为编译期静态路径（见 `@platform-routes`），无 `:platform` 动态段。
 * `/features/channel` 重定向至当前平台的管理后台。
 * 后端不可用走 `/503`；授权门控在 WorkspaceOutlet 路由级处理。
 *
 * @author coisini
 * @created 2026-07-21
 */

import { createBrowserRouter, Navigate } from "react-router";
import { CHANNEL_MANAGE_ROOT } from "@desk/platform/compile";
import { routeSegments } from "@platform-routes";

import { AccessGate } from "../app/access-gate";
import { ServiceUnavailablePage } from "../app/pages/service-unavailable-page";
import { AppShell } from "../app/shell";
import { DISCOVERY_AVAILABLE } from "@feature/discovery";

/**
 * 占位路由节点：实际页面由 {@link AppShell} 内 WorkspaceOutlet 按 pathname 懒加载。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */
function WorkspacePathMarker() {
  return null;
}

/** 为仅匹配 URL 的工作区路径补上 element，消除 React Router leaf 警告。 */
function workspaceRoute(path: string) {
  return { path, element: <WorkspacePathMarker /> };
}

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
      { index: true, element: <Navigate to={CHANNEL_MANAGE_ROOT} replace /> },
      workspaceRoute("features/ai"),
      workspaceRoute("features/chat"),
      ...(DISCOVERY_AVAILABLE ? [workspaceRoute("features/discovery")] : []),
      {
        path: "features/channel",
        element: <Navigate to={CHANNEL_MANAGE_ROOT} replace />,
      },
      ...routeSegments.map((segment) => ({
        ...segment,
        element: <WorkspacePathMarker />,
      })),
      workspaceRoute("features/knowledge"),
    ],
  },
]);
