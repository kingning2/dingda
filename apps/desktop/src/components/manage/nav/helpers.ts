import type { ManageNavGroup, ManageNavItem } from "./types";

/** 解析分组内已接入的导航项（保持 nav 中的顺序）。 */
export function manageNavItemsForGroup<V extends string>(
  group: ManageNavGroup<V>,
  nav: ManageNavItem<V>[],
): ManageNavItem<V>[] {
  const byKey = new Map(nav.map((item) => [item.key, item]));
  return group.keys
    .map((key) => byKey.get(key))
    .filter((item): item is ManageNavItem<V> => item != null && item.ready);
}

/** 侧栏可见分组（去掉全部子项未接入后的空组）。 */
export function visibleManageNavGroups<V extends string>(
  groups: ManageNavGroup<V>[],
  nav: ManageNavItem<V>[],
): Array<ManageNavGroup<V> & { items: ManageNavItem<V>[] }> {
  return groups
    .map((group) => ({ ...group, items: manageNavItemsForGroup(group, nav) }))
    .filter((group) => group.items.length > 0);
}

/** 由 nav 生成 URL 片段 → 中文标题映射。 */
export function navTitles<V extends string>(nav: ManageNavItem<V>[]): Record<V, string> {
  return Object.fromEntries(nav.map((item) => [item.key, item.label])) as Record<V, string>;
}

/** 判断字符串是否为合法管理子页面 key。 */
export function isManageView<V extends string>(
  titles: Record<V, string>,
  value: string,
): value is V {
  return value in titles;
}
