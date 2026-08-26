/**
 * 前端启动生命周期埋点（中文 + 本段耗时）。
 *
 * `sinceNavMs` 从 WebView 导航起点算（含 HTML/JS 下载与执行）。
 * `sinceJsMs` 从本模块执行算（Vite 转换完成后）。
 *
 * @author Xiaoman
 * @created 2026-08-24
 */

import { logWrite } from "@desk/platform/ipc/log";

const jsStartAt = performance.now();

const loggedPhases = new Set<string>();
let lastSinceJsMs = 0;

type StartupMark = {
  phase: string;
  atMs: number;
};

declare global {
  interface Window {
    __DINGDA_STARTUP_MARKS?: StartupMark[];
  }
}

const PHASE_LABELS: Record<string, string> = {
  "frontend.html": "HTML 就绪",
  "frontend.js.entry": "JS 入口",
  "frontend.react.mounted": "React 已挂载",
  "frontend.gate.blocking": "授权闸门等待中",
  "frontend.gate.redirect-503": "闸门跳转服务不可用",
  "frontend.gate.open": "授权闸门已放行",
  "frontend.license.fetch.begin": "开始拉取授权状态",
  "frontend.license.fetch.end": "授权状态拉取完成",
  "frontend.shell.ready": "工作区壳就绪",
  "frontend.first-paint": "首屏绘制完成",
};

function phaseLabel(phase: string): string {
  return PHASE_LABELS[phase] ?? `未登记阶段(${phase})`;
}

function formatNav(entry: PerformanceNavigationTiming | undefined): string {
  if (!entry) {
    return "";
  }
  return ` | DNS ${entry.domainLookupEnd.toFixed(0)}ms | 响应 ${entry.responseEnd.toFixed(0)}ms | DOM可交互 ${entry.domInteractive.toFixed(0)}ms`;
}

/**
 * 上报一个启动阶段。同名阶段只打一次（避免 StrictMode 刷屏）。
 *
 * @param phase - 阶段名，如 `frontend.js.entry`
 * @param extra - 附加字段文本（已含前导分隔）
 */
export function logStartupPhase(phase: string, extra = ""): void {
  if (loggedPhases.has(phase)) {
    return;
  }
  loggedPhases.add(phase);
  const sinceNavMs = Math.round(performance.now());
  const sinceJsMs = Math.round(performance.now() - jsStartAt);
  const deltaMs = Math.max(0, sinceJsMs - lastSinceJsMs);
  lastSinceJsMs = sinceJsMs;
  const label = phaseLabel(phase);
  void logWrite(
    `[启动] ${label} | 本段 ${deltaMs}ms | 自JS ${sinceJsMs}ms | 自导航 ${sinceNavMs}ms${extra}`,
    "INFO",
  ).catch(() => {});
}

/**
 * 把 index.html 内联脚本记下的时间点刷进日志。
 */
export function flushHtmlStartupMarks(): void {
  const marks = window.__DINGDA_STARTUP_MARKS ?? [];
  for (const mark of marks) {
    if (loggedPhases.has(mark.phase)) {
      continue;
    }
    loggedPhases.add(mark.phase);
    const sinceNavMs = Math.round(mark.atMs);
    const jsGapMs = Math.round(jsStartAt - mark.atMs);
    const label = phaseLabel(mark.phase);
    void logWrite(
      `[启动] ${label} | 自导航 ${sinceNavMs}ms | 距JS入口 ${jsGapMs}ms`,
      "INFO",
    ).catch(() => {});
  }
}

/**
 * 工作区页面完成首次绘制后记录首屏。
 *
 * @param route - 首屏对应路由
 */
export function logFirstScreenRender(route: string): void {
  const nav = performance.getEntriesByType("navigation")[0] as
    | PerformanceNavigationTiming
    | undefined;
  logStartupPhase("frontend.first-paint", ` | 路由=${route}${formatNav(nav)}`);
}
