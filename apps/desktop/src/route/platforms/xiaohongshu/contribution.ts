/**
 * 小红书路由链 — 选品产品不注册 manage / 搜索页，仅账号。
 */

import type { PlatformRouteContribution } from "../types";

/** 小红书路由 contribution（无管理台页面）。 */
export const xiaohongshuRouteContribution: PlatformRouteContribution = {
  routeSegments: [],
  pageLoaders: {},
  manageNavGroups: [],
  platformCapabilities: ["account"],
  manageTitleFromPath: () => null,
};
