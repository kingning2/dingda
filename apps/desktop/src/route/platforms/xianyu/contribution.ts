/**
 * 闲鱼路由链步骤 — 启用时追加路由 / 导航 / 页面加载器。
 */

import { CHANNEL_MANAGE_ROOT, managePath } from "@desk/platform/compile";

import {
  MANAGE_NAV,
  MANAGE_NAV_GROUPS,
  MANAGE_VIEW_TITLES,
  isManageView,
  manageNavItemsForGroup,
} from "@feature/platform/xianyu/manage-nav";

import type { PageLoader, PlatformRouteContribution } from "../types";

function toRouteSegment(fullPath: string): string {
  return fullPath.replace(/^\//, "");
}

const loadManageConsole: PageLoader = async () => {
  const { XianyuManageConsole } = await import("@feature/platform/xianyu/manage-console");
  return XianyuManageConsole;
};

function buildXianyuRoutes(): PlatformRouteContribution {
  return {
    routeSegments: [
      { path: toRouteSegment(CHANNEL_MANAGE_ROOT) },
      ...MANAGE_NAV.map((item) => {
        const locked = item.key === "accounts";
        return locked
          ? { path: toRouteSegment(managePath(item.key)), locked: true as const }
          : { path: toRouteSegment(managePath(item.key)) };
      }),
      { path: `${toRouteSegment(managePath("items"))}/:itemId` },
    ],
    pageLoaders: {
      [CHANNEL_MANAGE_ROOT]: loadManageConsole,
      ...Object.fromEntries(
        MANAGE_NAV.map((item) => [managePath(item.key), loadManageConsole]),
      ),
    },
    manageNavGroups: MANAGE_NAV_GROUPS.map((group) => ({
      label: group.label,
      icon: group.icon,
      keys: group.keys,
      items: manageNavItemsForGroup(group),
    })).filter((group) => group.items.length > 0),
    platformCapabilities: ["chat", "order", "account", "manage"],
    manageTitleFromPath(pathname: string): string | null {
      if (pathname === CHANNEL_MANAGE_ROOT) {
        return "首页";
      }
      const prefix = `${CHANNEL_MANAGE_ROOT}/`;
      if (!pathname.startsWith(prefix)) {
        return null;
      }
      const rest = pathname.slice(prefix.length);
      if (rest.startsWith("items/") && rest.split("/").length >= 2) {
        return "商品详情";
      }
      const view = rest.split("/")[0] ?? "";
      if (isManageView(view)) {
        return MANAGE_VIEW_TITLES[view];
      }
      return null;
    },
  };
}

/** 闲鱼路由 contribution（仅编译期启用闲鱼时由 Vite 插件 import）。 */
export const xianyuRouteContribution: PlatformRouteContribution = buildXianyuRoutes();
