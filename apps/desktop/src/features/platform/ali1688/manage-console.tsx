/**
 * 1688 管理子页出口 — 共享路由骨架 + 1688 配置（VIEW_PAGES）。
 */
import { type ComponentType } from "react";
import { ManageConsole, type ManageConsoleConfig } from "@components/manage/console";
import { Ali1688AccountsPage } from "./accounts";
import { Ali1688SearchPage } from "./search";
import { isManageView, type ManageView } from "./manage-nav";

const VIEW_PAGES: Record<ManageView, ComponentType> = {
  accounts: Ali1688AccountsPage,
  search: Ali1688SearchPage,
};

const config: ManageConsoleConfig<ManageView> = {
  fallback: "search",
  viewPages: VIEW_PAGES,
  isView: isManageView,
};

/** 1688 管理子页出口（静态 URL → 业务页）。 */
export function Ali1688ManageConsole() {
  return <ManageConsole config={config} />;
}
