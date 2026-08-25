/**
 * 编译期平台路由入口 — 链式合并各站 contribution（Vite 插件按启用平台生成 import）。
 */

import { mergedPlatformRoutes, lockedRoutePaths } from "./chain";
import type { ManageNavGroup, ManageNavItem, PageLoader } from "./types";

export type { ManageNavGroup, ManageNavItem, PageLoader };

export {
  MANAGE_VIEW_TITLES,
  isManageView,
} from "virtual:dingda/platform-manage-nav";

export type { ManageView } from "./types";

export const routeSegments = mergedPlatformRoutes.routeSegments;
export const pageLoaders = mergedPlatformRoutes.pageLoaders;
export const manageNavGroups = mergedPlatformRoutes.manageNavGroups;
export const platformCapabilities = mergedPlatformRoutes.platformCapabilities;
export const manageTitleFromPath = mergedPlatformRoutes.manageTitleFromPath;
export { lockedRoutePaths };

/** 编译期平台管理导航（侧栏数据源）。 */
export const manageNav = manageNavGroups.flatMap((group) => group.items);
