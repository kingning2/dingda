/**
 * Discovery 二级壳 — Tab + 开始选品入口。
 */

import type { ReactNode } from "react";
import { Button, PageScaffold } from "@desk/ui";
import { SubNavTabs } from "@components/product-shell";
import { useLocation } from "react-router";
import { useWorkspaceNav } from "../../app/use-workspace-tabs";

const DISCOVERY_TABS = [
  { path: "/discovery/high-profit", label: "高利润" },
  { path: "/discovery/hot", label: "热门" },
  { path: "/discovery/blue-ocean", label: "蓝海" },
  { path: "/discovery/new", label: "新发现" },
  { path: "/discovery/start", label: "开始选品" },
];

export interface DiscoveryShellProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  ambient?: "spotlight" | "none";
}

/** 选品发现页统一壳。 */
export function DiscoveryShell({
  title,
  subtitle,
  children,
  ambient = "none",
}: DiscoveryShellProps) {
  const { pathname } = useLocation();
  const { selectTab } = useWorkspaceNav();

  return (
    <PageScaffold
      title={title}
      subtitle={subtitle}
      ambient={ambient}
      containerPadding="sm"
      toolbar={<SubNavTabs tabs={DISCOVERY_TABS} activePath={pathname} />}
      extra={
        pathname === "/discovery/start" ? undefined : (
          <Button type="button" size="sm" onClick={() => selectTab("/discovery/start")}>
            开始选品
          </Button>
        )
      }
    >
      {children}
    </PageScaffold>
  );
}
