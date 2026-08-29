/**
 * 监控 Feature。
 */

import { Bell } from "@desk/ui/icons";

export { MonitoringSubscriptionsPage } from "./subscriptions-page";
export { MonitoringAlertsPage } from "./alerts-page";
export { MonitoringRulesPage } from "./rules-page";

export const MONITORING_PATH = "/monitoring" as const;

export const monitoringFeature = {
  id: "monitoring",
  path: MONITORING_PATH,
  navItem: {
    id: "monitoring",
    path: MONITORING_PATH,
    label: "价格 / 竞品监控",
    icon: Bell,
  },
};
