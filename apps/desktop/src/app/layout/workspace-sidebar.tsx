/**
 * 工作区侧栏 — 选品业务一级导航 + 底栏设置。
 *
 * 不展示客服 / AI / 平台「交易」分组。
 */

import { useMemo } from "react";
import {
  DesktopSidebar,
  SidebarFooter,
  SidebarHeader,
  SidebarLink,
  SidebarToggle,
} from "@desk/ui";
import { Settings } from "@desk/ui/icons";
import { listWorkspaceFeatures, type WorkspaceFeature } from "@feature/workspace-features";

/** L1 点击时落到默认二级路由。 */
const DEFAULT_CHILD_PATH: Record<string, string> = {
  "/discovery": "/discovery/high-profit",
  "/profit": "/profit/calculator",
  "/monitoring": "/monitoring/subscriptions",
  "/settings": "/settings/general",
};

/**
 * 工作区侧栏属性。
 */
export interface WorkspaceSidebarProps {
  /** 当前激活路径。 */
  activePath: string;
  /** 选择标签页/路由。 */
  onNavigate: (path: string) => void;
}

function isNavActive(activePath: string, targetPath: string): boolean {
  if (targetPath === "/") {
    return activePath === "/";
  }
  return activePath === targetPath || activePath.startsWith(`${targetPath}/`);
}

function FeatureNavLink({
  feature,
  activePath,
  onNavigate,
}: {
  feature: WorkspaceFeature;
  activePath: string;
  onNavigate: (path: string) => void;
}) {
  const Icon = feature.navItem.icon;
  const target = DEFAULT_CHILD_PATH[feature.path] ?? feature.path;
  return (
    <SidebarLink
      label={feature.navItem.label}
      icon={<Icon className="size-[1.125rem]" aria-hidden />}
      active={isNavActive(activePath, feature.path)}
      onClick={() => onNavigate(target)}
    />
  );
}

/**
 * 桌面工作区左侧导航。
 */
export function WorkspaceSidebar({ activePath, onNavigate }: WorkspaceSidebarProps) {
  const headerFeatures = useMemo(() => listWorkspaceFeatures("header"), []);

  return (
    <DesktopSidebar className="min-h-0">
      <div className="flex h-full min-h-0 flex-col">
        <SidebarHeader>
          {headerFeatures.map((feature) => (
            <FeatureNavLink
              key={feature.id}
              feature={feature}
              activePath={activePath}
              onNavigate={onNavigate}
            />
          ))}
        </SidebarHeader>

        <div className="min-h-0 flex-1" aria-hidden />

        <SidebarFooter className="mt-auto space-y-2 border-t border-border pt-2">
          <SidebarLink
            label="设置"
            icon={<Settings className="size-[1.125rem]" aria-hidden />}
            active={isNavActive(activePath, "/settings")}
            onClick={() => onNavigate("/settings/general")}
          />
          <SidebarToggle placement="footer" />
        </SidebarFooter>
      </div>
    </DesktopSidebar>
  );
}
