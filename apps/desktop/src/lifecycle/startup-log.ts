/**
 * 前端启动生命周期埋点。
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

type StartupMark = {
  phase: string;
  atMs: number;
};

declare global {
  interface Window {
    __DINGDA_STARTUP_MARKS?: StartupMark[];
  }
}

function formatNav(entry: PerformanceNavigationTiming | undefined): string {
  if (!entry) {
    return "";
  }
  const parts = [
    `dns=${entry.domainLookupEnd.toFixed(0)}`,
    `response=${entry.responseEnd.toFixed(0)}`,
    `domInteractive=${entry.domInteractive.toFixed(0)}`,
  ];
  return ` ${parts.join(" ")}`;
}

/**
 * 上报一个启动阶段。同名阶段只打一次（避免 StrictMode 刷屏）。
 *
 * @param phase - 阶段名，如 `frontend.js.entry`
 * @param extra - 附加字段文本（已含前导空格）
 */
export function logStartupPhase(phase: string, extra = ""): void {
  if (loggedPhases.has(phase)) {
    return;
  }
  loggedPhases.add(phase);
  const sinceNavMs = performance.now().toFixed(0);
  const sinceJsMs = (performance.now() - jsStartAt).toFixed(0);
  void logWrite(
    `[startup] phase=${phase} sinceNavMs=${sinceNavMs} sinceJsMs=${sinceJsMs}${extra}`,
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
    const jsGapMs = (jsStartAt - mark.atMs).toFixed(0);
    void logWrite(
      `[startup] phase=${mark.phase} sinceNavMs=${mark.atMs.toFixed(0)} jsGapMs=${jsGapMs}`,
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
  logStartupPhase("frontend.first-paint", ` route=${route}${formatNav(nav)}`);
}
