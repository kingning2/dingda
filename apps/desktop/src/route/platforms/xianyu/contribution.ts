/**
 * 闲鱼路由链 — 选品产品不再注册 manage 业务页；仅锁定设置账号路由。
 */

import type { PlatformRouteContribution } from "../types";

/** 闲鱼路由 contribution（无管理台页面）。 */
export const xianyuRouteContribution: PlatformRouteContribution = {
  routeSegments: [{ path: "settings/accounts", locked: true }],
  pageLoaders: {},
  manageNavGroups: [],
  platformCapabilities: ["account"],
  manageTitleFromPath: () => null,
};
