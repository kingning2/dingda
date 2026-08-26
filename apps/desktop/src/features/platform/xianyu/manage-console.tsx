/**
 * 闲鱼管理子页出口 — 共享路由骨架 + 闲鱼配置（VIEW_PAGES / 深链）。
 *
 * 导航入口由应用主侧栏提供；风控日志与免责声明在应用设置弹窗中。
 */
import { type ComponentType } from "react";
import { managePath } from "@desk/platform/compile";
import { ManageConsole, type ManageConsoleConfig } from "@components/manage/console";
import { XianyuAccountsPage } from "./accounts";
import { XianyuDashboardPage } from "./dashboard";
import { XianyuItemsPage } from "./items";
import { XianyuItemDetailPage } from "./item-detail";
import { XianyuOrdersPage } from "./orders";
import { isManageView, type ManageView } from "./manage-nav";

/**
 * view → 页面组件映射。
 * 仅保留当前管理台需要的业务页。
 */
const VIEW_PAGES: Partial<Record<ManageView, ComponentType>> = {
  dashboard: XianyuDashboardPage,
  accounts: XianyuAccountsPage,
  items: XianyuItemsPage,
  orders: XianyuOrdersPage,
};

/** 从路径解析商品详情 ID（`/manage/items/:itemId`）。 */
function itemIdFromPathname(pathname: string): string | null {
  const prefix = `${managePath("items")}/`;
  if (!pathname.startsWith(prefix)) {
    return null;
  }
  const segment = pathname.slice(prefix.length).split("/")[0] ?? "";
  return segment ? decodeURIComponent(segment) : null;
}

const config: ManageConsoleConfig<ManageView> = {
  fallback: "dashboard",
  viewPages: VIEW_PAGES,
  isView: isManageView,
  deepLinks: [
    (pathname) => {
      const itemId = itemIdFromPathname(pathname);
      return itemId ? <XianyuItemDetailPage itemId={itemId} /> : null;
    },
  ],
};

/** 闲鱼管理子页出口（静态 URL → 业务页）。 */
export function XianyuManageConsole() {
  return <ManageConsole config={config} />;
}
