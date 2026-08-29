/**
 * 监控二级壳共用 Tab。
 */

import type { ReactNode } from "react";
import { PageScaffold } from "@desk/ui";
import { SubNavTabs } from "@components/product-shell";
import { useLocation } from "react-router";

const TABS = [
  { path: "/monitoring/subscriptions", label: "监控列表" },
  { path: "/monitoring/alerts", label: "提醒" },
  { path: "/monitoring/rules", label: "规则" },
];

export function MonitoringShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  const { pathname } = useLocation();
  return (
    <PageScaffold
      title={title}
      subtitle={subtitle}
      ambient="none"
      containerPadding="sm"
      toolbar={<SubNavTabs tabs={TABS} activePath={pathname} />}
    >
      {children}
    </PageScaffold>
  );
}
