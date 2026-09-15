/**
 * 页面级共享工具：探测、等待、真实点击、导航。
 *
 * account-qr 与 agent-runtimes 两条 spec 的共同底座，抽出来避免两处漂移。
 *
 * ## 性能陷阱（本层最贵的一个坑，务必保留处理）
 * `@wdio/tauri-service` 的 `beforeCommand` 会对
 * `getTitle / $ / $$ / findElement(s) / elementClick` 先跑
 * `ensureActiveWindowFocus`；它内部要 `getWindowStates`，而本机环境里这一步每次都
 * 失败并**等满 5 秒**：
 *   WARN tauri-service:window: Failed to get window states:
 *     Error: Tauri core.invoke not available after 5s timeout
 * 于是**每个元素操作都多花 5 秒**。两道解法：
 *   1. `disableAutoFocus()` —— 调一次 `switchWindow` 置上 `suppressActiveWindowFocus`，
 *      之后自动聚焦全部跳过（见 tauri-service 的 `switchWindowByLabel` 实现）；
 *   2. 高频轮询一律走 `browser.execute` —— `execute` **不在** focusCommands 列表里。
 */
import { $$, browser } from "@wdio/globals";

/** 应用窗口 label（packages-rs/client/tauri.conf.json）。 */
export const WINDOW_LABEL = "main";

/** 带时间戳的日志：这类用例的失败几乎都是「卡在哪一步」，时间差是最有用的信息。 */
export function log(scope: string, message: string): void {
  const stamp = new Date().toISOString().slice(11, 19);
  console.log(`[${scope} ${stamp}] ${message}`);
}

/** 页面状态一次性抓回：比多次 `$` 查询便宜得多。 */
export type PageProbe = {
  hash: string;
  splashPresent: boolean;
  navRailPresent: boolean;
  dialogText: string | null;
  buttons: string[];
  bodyHead: string;
};

export function probePage(): Promise<PageProbe> {
  return browser.execute(() => {
    const dialog = document.querySelector('[data-slot="dialog-content"]');
    return {
      hash: window.location.hash,
      splashPresent: Boolean(document.querySelector("#boot-splash")),
      navRailPresent: Boolean(document.querySelector('nav[aria-label="主导航"]')),
      dialogText: dialog
        ? (dialog.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 300)
        : null,
      buttons: Array.from(document.querySelectorAll("button"))
        .map((button) => (button.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 24))
        .filter(Boolean)
        .slice(0, 40),
      bodyHead: (document.body.innerText ?? "").replace(/\s+/g, " ").slice(0, 240),
    };
  });
}

/** 现场快照，用于失败时定位。 */
export async function dumpContext(): Promise<string> {
  try {
    return JSON.stringify(await probePage(), null, 2);
  } catch (error) {
    return `（抓取现场失败：${String(error)}）`;
  }
}

/** 通用轮询：`check` 返回真即结束；超时返回 false。 */
export async function waitUntil(
  check: () => Promise<boolean>,
  timeoutMs: number,
  intervalMs = 300,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await check()) return true;
    await browser.pause(intervalMs);
  }
  return false;
}

/** 跳过 tauri-service 的「命令前自动聚焦」，每个元素操作省 5 秒。失败不致命。 */
export async function disableAutoFocus(): Promise<void> {
  try {
    await browser.tauri.switchWindow(WINDOW_LABEL);
    log("ui", "已跳过 tauri-service 自动聚焦（每个命令省 5s）");
  } catch (error) {
    console.warn(`[ui] 跳过自动聚焦失败（不致命，只是变慢）：${String(error)}`);
  }
}

/** 等应用壳渲染完成：启动屏被移除 **且** 主导航出现。 */
export async function waitForAppShell(timeoutMs = 90_000): Promise<boolean> {
  return waitUntil(async () => {
    const page = await probePage();
    return !page.splashPresent && page.navRailPresent;
  }, timeoutMs);
}

/**
 * 按可见文本找按钮。
 *
 * 只依赖 `$$("button")` + `getText()` —— 这两个最稳，不用 `*=text` 文本选择器
 * （各版本语法有差异）也不用 XPath。
 */
export async function findButtonByText(
  text: string,
  mode: "exact" | "contains" = "contains",
): Promise<WebdriverIO.Element | null> {
  const buttons = await $$("button");
  for (const button of buttons) {
    let label = "";
    try {
      label = (await button.getText()).trim();
    } catch {
      continue; // 元素在遍历途中被卸载，跳过
    }
    if (mode === "exact" ? label === text : label.includes(text)) return button;
  }
  return null;
}

/**
 * 点侧栏主导航项（`nav[aria-label="主导航"]` 里的按钮，见 ui-layout/entry-nav-rail.tsx）。
 * 这是**真实点击**；不通过改 hash 走路由。
 */
export async function clickNavItem(label: string): Promise<void> {
  const item = await findButtonByText(label, "exact");
  if (!item) {
    throw new Error(`侧栏主导航里找不到「${label}」\n现场快照：${await dumpContext()}`);
  }
  await item.click();
}
