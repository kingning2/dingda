export type EntryView =
  | "home"
  | "projects"
  | "plugins"
  | "agents"
  | "accounts"
  | "monitor";

const ENTRY_PATHS: Record<EntryView, string> = {
  home: "/",
  projects: "/projects",
  plugins: "/plugins",
  agents: "/agents",
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
  agents: "/agents",
  accounts: "/accounts",
  /** @deprecated 使用 /agents 或 /accounts */
  assets: "/assets",
  monitor: "/monitor",
  work: (workId: string) => `/work/${encodeURIComponent(workId)}`,
  errorTest: "/error-test",
  notImplemented: "/501",
} as const;

export function entryPath(view: EntryView): string {
  return ENTRY_PATHS[view];
}

/** 侧栏高亮：工作详情页沿用首页选中态（与旧版 hash 路由一致）。 */
export function entryViewFromPathname(pathname: string): EntryView {
  if (pathname.startsWith("/work/")) return "home";
  // 旧「资产」入口：按 query 或默认落到 Agent
  if (pathname === "/assets" || pathname.startsWith("/assets/")) return "agents";
  return PATH_TO_ENTRY.get(pathname) ?? "home";
}

export function createWorkId(): string {
  return `work-${Date.now()}`;
}
