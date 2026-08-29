/**
 * Dashboard Feature — 工作台（今天卖什么）。
 */

import { LayoutDashboard } from "@desk/ui/icons";

export { DashboardPage } from "./dashboard-page";

export const DASHBOARD_PATH = "/dashboard" as const;

export const dashboardFeature = {
  id: "dashboard",
  path: DASHBOARD_PATH,
  navItem: {
    id: "dashboard",
    path: DASHBOARD_PATH,
    label: "工作台",
    icon: LayoutDashboard,
  },
};
