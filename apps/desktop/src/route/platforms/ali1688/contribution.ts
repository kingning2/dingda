/**
 * 1688 路由链 — 选品产品不再注册 manage / 搜索页。
 */

import type { PlatformRouteContribution } from "../types";

/** 1688 路由 contribution（无管理台页面）。 */
export const ali1688RouteContribution: PlatformRouteContribution = {
  routeSegments: [],
  pageLoaders: {},
  manageNavGroups: [],
  platformCapabilities: ["account"],
  manageTitleFromPath: () => null,
};
