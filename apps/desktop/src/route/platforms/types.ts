/**
 * 平台路由链 — 各站 contribution 与合并结果类型。
 */

import type { ComponentType } from "react";
import type { LucideIcon } from "@desk/ui/icons";

/** 页面懒加载工厂。 */
export type PageLoader = () => Promise<ComponentType>;

/** 路由段。 */
export interface RouteSegment {
  path: string;
  /** 标记为 true 时该路由需要有效 license 才能访问。 */
  locked?: true;
}

/** 管理子页 key（各站 manage-nav 并集；具体校验见 `isManageView`）。 */
export type ManageView = string;

/** 侧栏管理导航项（各站 contribution 共用形状）。 */
export interface ManageNavItem {
  key: string;
  label: string;
  icon: LucideIcon;
  description: string;
  ready: boolean;
}

/** 侧栏分组。 */
export interface ManageNavGroup {
  label: string;
  icon: LucideIcon;
  keys: string[];
}

/** 单站路由 contribution。 */
export interface PlatformRouteContribution {
  routeSegments: RouteSegment[];
  pageLoaders: Record<string, PageLoader>;
  manageNavGroups: Array<ManageNavGroup & { items: ManageNavItem[] }>;
  platformCapabilities: readonly string[];
  manageTitleFromPath: (pathname: string) => string | null;
}

/** 空 contribution — 未启用平台或双站下由主站接管时透传。 */
export const EMPTY_PLATFORM_ROUTE_CONTRIBUTION: PlatformRouteContribution = {
  routeSegments: [],
  pageLoaders: {},
  manageNavGroups: [],
  platformCapabilities: [],
  manageTitleFromPath: () => null,
};
