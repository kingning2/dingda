/**
 * 闲鱼管理子页面导航配置 — 类型与助手来自共享 `components/manage/nav/`，
 * 本文件只提供闲鱼侧配置。
 *
 * `ready: false` 的项仍保留路由与页面，但侧栏不展示（未接入平台能力）。
 */
import type { ManageNavGroup, ManageNavItem } from "@components/manage/nav";
import {
  isManageView as isManageViewFor,
  manageNavItemsForGroup as itemsForGroup,
  navTitles,
  visibleManageNavGroups as visibleGroups,
} from "@components/manage/nav";
import { Building2, Package, Radar, Search, ShoppingCart, Users } from "@desk/ui/icons";

export type { ManageNavGroup, ManageNavItem } from "@components/manage/nav";
export { managePath } from "@desk/platform/compile";

/** 闲鱼管理子页面标识（URL 片段，如 `/manage/accounts`）。 */
export type ManageView =
  | "dashboard"
  | "accounts"
  | "accounts-1688"
  | "search"
  | "search-1688"
  | "monitor"
  | "items"
  | "orders";

/** 全部管理子页面（对齐原前端 Sidebar；侧栏仅渲染 `ready` 项）。 */
export const MANAGE_NAV: ManageNavItem<ManageView>[] = [
  {
    key: "accounts",
    label: "账号管理",
    icon: Users,
    description: "闲鱼 / 1688 分 Tab 扫码登录与连接状态",
    ready: true,
  },
  {
    key: "search",
    label: "闲鱼商品搜索",
    icon: Search,
    description: "关键词搜索闲鱼二手商品",
    ready: true,
  },
  {
    key: "monitor",
    label: "商品监控",
    icon: Radar,
    description: "定时扫描商品，AI 自动筛选并推荐入库",
    ready: true,
  },
  ...(__DINGDA_HAS_ALI1688__
    ? [
        {
          key: "accounts-1688" as const,
          label: "1688账号",
          icon: Building2,
          description: "打开账号管理并定位 1688 账号",
          ready: false,
        },
        {
          key: "search-1688" as const,
          label: "1688商品搜索",
          icon: Search,
          description: "关键词搜索 1688 批发商品",
          ready: true,
        },
      ]
    : []),
  {
    key: "items",
    label: "商品管理",
    icon: Package,
    description: "商品列表、筛选与 AI 提示词",
    ready: true,
  },
  {
    key: "orders",
    label: "订单管理",
    icon: ShoppingCart,
    description: "订单列表、筛选与状态更新",
    ready: true,
  },
];

/** 侧栏分组导航 — 保留的管理子页按业务域归类。 */
export const MANAGE_NAV_GROUPS: ManageNavGroup<ManageView>[] = [
  { label: "交易", icon: ShoppingCart, keys: ["accounts", "search", "monitor", "items", "orders"] },
  ...(__DINGDA_HAS_ALI1688__
    ? [{ label: "1688", icon: Building2, keys: ["search-1688"] as ManageView[] }]
    : []),
];

/** 解析分组内已接入的导航项（保持 MANAGE_NAV 中的顺序）。 */
export function manageNavItemsForGroup(
  group: ManageNavGroup<ManageView>,
): ManageNavItem<ManageView>[] {
  return itemsForGroup(group, MANAGE_NAV);
}

/** 侧栏可见分组（去掉全部子项未接入后的空组）。 */
export function visibleManageNavGroups(): Array<
  ManageNavGroup<ManageView> & { items: ManageNavItem<ManageView>[] }
> {
  return visibleGroups(MANAGE_NAV_GROUPS, MANAGE_NAV);
}

/** @deprecated 侧栏已展示全部子页，首页不再使用 */
export const SIDEBAR_MANAGE_VIEWS: ManageView[] = ["accounts", "items", "orders"];

/** @deprecated 侧栏已展示全部子页，首页不再使用 */
export const HOME_MANAGE_NAV: ManageNavItem<ManageView>[] = MANAGE_NAV.filter(
  (item) => !SIDEBAR_MANAGE_VIEWS.includes(item.key) && item.ready,
);

/** 管理子页面 URL 片段 → 中文标题（标签页 / 面包屑）。 */
export const MANAGE_VIEW_TITLES: Record<ManageView, string> = navTitles(MANAGE_NAV);

/** 判断字符串是否为合法管理子页面 key。 */
export function isManageView(value: string): value is ManageView {
  return isManageViewFor(MANAGE_VIEW_TITLES, value);
}
