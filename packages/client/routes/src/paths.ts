/**
 * 入口视图与路径常量。
 *
 * 职责：
 *     声明主导航有哪几个入口（`EntryView`）、各自的路径，以及「路径 → 入口」的反查。
 *
 * 设计说明：
 *     - `EntryView` 只装**主导航**里的入口。模型配置这类「设置向」页面有自己的路径
 *       （`paths.modelConfig`）但不进 `EntryView` —— 它在设置菜单里，不是日常视图
 *     - 原来的 `agents` 入口已随外部 CLI 对接一并删除，`/agents` 路由不复存在。
 *       留一个指向 404 的常量比没有更糟，所以连 `EntryView` 成员一起删掉
 */

export type EntryView =
  | "home"
  | "projects"
  | "plugins"
  | "accounts"
  | "monitor";

const ENTRY_PATHS: Record<EntryView, string> = {
  home: "/",
  projects: "/projects",
  plugins: "/plugins",
  accounts: "/accounts",
  monitor: "/monitor",
};

const PATH_TO_ENTRY = new Map<string, EntryView>(
  Object.entries(ENTRY_PATHS).map(([view, path]) => [path, view as EntryView]),
);

export const paths = {
  home: "/",
  projects: "/projects",
  plugins: "/plugins",
  accounts: "/accounts",
  /** @deprecated 资产页已拆成账号页与模型配置页，本路径只作历史链接兼容。 */
  assets: "/assets",
  monitor: "/monitor",
  /** 模型配置（供应商与 API Key）。入口在设置菜单里，不在主导航 —— 它不是日常视图。 */
  modelConfig: "/model-config",
  work: (workId: string) => `/work/${encodeURIComponent(workId)}`,
  errorTest: "/error-test",
  notImplemented: "/501",
} as const;

export function entryPath(view: EntryView): string {
  return ENTRY_PATHS[view];
}

/** 侧栏高亮：工作详情页与设置向页面（模型配置）都沿用首页选中态。 */
export function entryViewFromPathname(pathname: string): EntryView {
  if (pathname.startsWith("/work/")) return "home";
  return PATH_TO_ENTRY.get(pathname) ?? "home";
}

export function createWorkId(): string {
  return `work-${Date.now()}`;
}
