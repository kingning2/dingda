/**
 * 桌面端数据对接清单 — 官网控制台演示后续替换点。
 *
 * 当前为方案 A 骨架 + MOCK 数据（见 `content/business.ts`）。
 * 桌面端就绪后，按路由替换为 Tauri IPC 或共享 API。
 */

export const DESKTOP_DATA_PORTS = {
  dashboard: {
    route: "/console",
    desktop: "/dashboard",
    ipc: ["dashboard_stats"],
    mock: "MOCK_STATS, DASHBOARD_SECTIONS",
  },
  discovery: {
    route: "/console/discovery/*",
    desktop: "/discovery/*",
    ipc: ["discovery list APIs (待桌面端暴露)"],
    mock: "MOCK_OPPORTUNITIES",
  },
  discoveryStart: {
    route: "/console/discovery/start",
    desktop: "/discovery/start",
    ipc: ["agentRunStart (price_compare)"],
    mock: "表单仅演示，不发起真实任务",
  },
  products: {
    route: "/console/products",
    desktop: "/products",
    ipc: ["item_list"],
    mock: "MOCK_PRODUCTS",
  },
  tasks: {
    route: "/console/tasks",
    desktop: "/tasks",
    ipc: ["agentRunList", "agentRunStart"],
    mock: "MOCK_TASKS",
  },
  profit: {
    route: "/console/profit/*",
    desktop: "/profit/*",
    ipc: ["待桌面端利润模块 IPC"],
    mock: "SimpleSkeletonPage",
  },
  monitoring: {
    route: "/console/monitoring/*",
    desktop: "/monitoring/*",
    ipc: ["待桌面端监控模块 IPC"],
    mock: "MonitoringSkeletonPage",
  },
  settings: {
    route: "/console/settings/*",
    desktop: "/settings/*",
    ipc: ["setting IPC + platform accounts"],
    mock: "SettingsSkeletonPage",
  },
} as const;
