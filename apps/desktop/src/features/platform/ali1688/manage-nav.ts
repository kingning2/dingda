/**
 * 1688 管理子页面导航 — 选品产品已取消 manage 业务页；空表兼容 virtual module。
 */
import type { ManageNavGroup, ManageNavItem } from "@components/manage/nav";
import {
  isManageView as isManageViewFor,
  manageNavItemsForGroup as itemsForGroup,
  navTitles,
} from "@components/manage/nav";

export type { ManageNavGroup, ManageNavItem } from "@components/manage/nav";
export { managePath } from "@desk/platform/compile";

export type ManageView = string;

export const MANAGE_NAV: ManageNavItem<ManageView>[] = [];

export const MANAGE_NAV_GROUPS: ManageNavGroup<ManageView>[] = [];

export function manageNavItemsForGroup(
  group: ManageNavGroup<ManageView>,
): ManageNavItem<ManageView>[] {
  return itemsForGroup(group, MANAGE_NAV);
}

export const MANAGE_VIEW_TITLES: Record<string, string> = navTitles(MANAGE_NAV);

export function isManageView(value: string): boolean {
  return isManageViewFor(MANAGE_VIEW_TITLES, value);
}
