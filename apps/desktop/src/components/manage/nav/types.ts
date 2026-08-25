import type { LucideIcon } from "@desk/ui/icons";

/** 管理子页面导航项（`V` = 平台自己的 ManageView 并集）。 */
export interface ManageNavItem<V extends string> {
  key: V;
  label: string;
  icon: LucideIcon;
  description: string;
  /** 是否已接入可用能力；`false`：侧栏隐藏（路由/页面仍保留）。 */
  ready: boolean;
}

/** 侧栏分组（Grouped Sidebar 模式）。 */
export interface ManageNavGroup<V extends string> {
  label: string;
  icon: LucideIcon;
  keys: V[];
}
