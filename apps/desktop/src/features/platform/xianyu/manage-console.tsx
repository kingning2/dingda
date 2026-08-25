/**
 * 闲鱼管理子页出口 — 共享路由骨架 + 闲鱼配置（VIEW_PAGES / 深链）。
 *
 * 导航入口由应用主侧栏提供；风控日志与免责声明在应用设置弹窗中。
 */
import { type ComponentType } from "react";
import { managePath } from "@desk/platform/compile";
import { ManageConsole, type ManageConsoleConfig } from "@components/manage/console";
import { Ali1688SearchPage } from "@feature/platform/ali1688/search";
import { XianyuMonitorPage } from "./monitor";
import { XianyuMonitorRunDetailPage } from "./monitor-run-detail";
import { XianyuMonitorTaskDetailPage } from "./monitor-task-detail";
import { XianyuSearchPage } from "./search";
import { XianyuAccountsPage } from "./accounts";
import { XianyuDashboardPage } from "./dashboard";
import { XianyuItemsPage } from "./items";
import { XianyuItemDetailPage } from "./item-detail";
import { XianyuOrdersPage } from "./orders";
import { isManageView, type ManageView } from "./manage-nav";
import { monitorTaskIdFromPathname } from "./monitor/monitor-utils";

/**
 * 兼容旧路由 `/manage/accounts-1688`：打开账号管理并定位 1688 Tab。
 * 双站构建时共享 Hub 同时含闲鱼 / 1688 Tab。
 */
function Accounts1688View() {
  return <XianyuAccountsPage initialTab="ali1688" />;
}

/**
 * view → 页面组件映射。
 * 1688 子页仅双站构建时注册（编译期裁剪，单站构建无该路由）。
 */
const VIEW_PAGES: Partial<Record<ManageView, ComponentType>> = {
  dashboard: XianyuDashboardPage,
  accounts: XianyuAccountsPage,
  search: XianyuSearchPage,
  monitor: XianyuMonitorPage,
  ...(__DINGDA_HAS_ALI1688__
    ? { "accounts-1688": Accounts1688View, "search-1688": Ali1688SearchPage }
    : {}),
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

/** 从路径解析监控运行详情 ID（`/manage/.../monitor/runs/:runId`）。 */
function monitorRunIdFromPathname(pathname: string): string | null {
  const prefix = `${managePath("monitor")}/runs/`;
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
    (pathname) => {
      const taskId = monitorTaskIdFromPathname(pathname);
      return taskId ? <XianyuMonitorTaskDetailPage taskId={taskId} /> : null;
    },
    (pathname) => {
      const runId = monitorRunIdFromPathname(pathname);
      return runId ? <XianyuMonitorRunDetailPage runId={runId} /> : null;
    },
  ],
};

/** 闲鱼管理子页出口（静态 URL → 业务页）。 */
export function XianyuManageConsole() {
  return <ManageConsole config={config} />;
}
