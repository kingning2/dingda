// 共享管理导航类型与助手（跨平台）。
export type { ManageNavGroup, ManageNavItem } from "./types";
export { isManageView, manageNavItemsForGroup, navTitles, visibleManageNavGroups } from "./helpers";
export { managePath } from "@desk/platform/compile";
