/**
 * 1688 管理子页面导航配置 — 类型与助手来自共享 `components/manage/nav/`，
 * 本文件只提供 1688 侧配置。
 *
 * 1688 站点仅提供账号管理（Cookie 扫码登录），无闲鱼业务子页。
 */
import type { ManageNavGroup, ManageNavItem } from "@components/manage/nav";
import {
  isManageView as isManageViewFor,
  manageNavItemsForGroup as itemsForGroup,
  navTitles,
} from "@components/manage/nav";
import { Search, ShoppingCart, Users } from "@desk/ui/icons";

export type { ManageNavGroup, ManageNavItem } from "@components/manage/nav";
export { managePath } from "@desk/platform/compile";

/** 1688 管理子页面标识（URL 片段，如 `/manage/accounts`）。 */
export type ManageView = "accounts" | "search";

/** 全部 1688 管理子页面。 */
export const MANAGE_NAV: ManageNavItem<ManageView>[] = [
  {
    key: "accounts",
    label: "账号管理",
    icon: Users,
    description: "1688 / 手机淘宝扫码登录与连接状态",
    ready: true,
  },
  {
    key: "search",
    label: "商品搜索",
    icon: Search,
    description: "关键词搜索 1688 批发商品",
    ready: true,
  },
];

/** 侧栏分组导航。 */
export const MANAGE_NAV_GROUPS: ManageNavGroup<ManageView>[] = [
  { label: "交易", icon: ShoppingCart, keys: ["search", "accounts"] },
];

/** 解析分组内已接入的导航项（保持 MANAGE_NAV 中的顺序）。 */
export function manageNavItemsForGroup(
  group: ManageNavGroup<ManageView>,
): ManageNavItem<ManageView>[] {
  return itemsForGroup(group, MANAGE_NAV);
}

/** 管理子页面 URL 片段 → 中文标题（标签页 / 面包屑）。 */
export const MANAGE_VIEW_TITLES: Record<ManageView, string> = navTitles(MANAGE_NAV);

/** 判断字符串是否为合法管理子页面 key。 */
export function isManageView(value: string): value is ManageView {
  return isManageViewFor(MANAGE_VIEW_TITLES, value);
}
