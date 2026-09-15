/**
 * 账号扫码流程 E2E：查账号 → 缺号或过期则走**页面按钮**扫码 → 阻塞等待扫码完成。
 *
 * 与 desktop-smoke.spec.ts 的分工：那个只验「壳层装配」；这里验「账号登录」这条真实链路。
 *
 * ## 驱动原则（重要）
 * 全程点页面上的按钮，**不直接打 `/v1/channel/qr/*` 推进流程**。测试进程只做两件
 * 「旁证」的事：扫码前读账号（决定要不要扫）、扫码后验账号（独立于前端自报）。
 * 唯一的例外是进账号页失败时的 hash 回落 —— 见 openAccountsPage 的说明。
 *
 * ## 选择器策略
 * 一律用我们自己的源码里写死的东西，不碰 CSS 类名和 Tailwind：
 *   - `[data-slot="tabs-trigger"]` / `[data-slot="dialog-content"]` /
 *     `[data-slot="dropdown-menu-item"]`：`ui-primitives` 里显式设的 `data-slot`
 *     （比 base-ui 派生的 `role` 更确定，不依赖上游实现细节）；
 *   - `img[alt="登录二维码"]`：`ui-account/account-qr-dialog.tsx` 里写死的 alt；
 *   - 按钮按**可见文本**在测试进程里筛，只用 `$$("button")` 这个最保险的 tag 选择器。
 *
 * 性能陷阱（每命令 5 秒的自动聚焦）与页面级工具见 `helpers/ui.ts`。
 *
 * ## 时间预算（决定了本文件的超时常量）
 * 闲鱼扫码的窗口由后端决定：`channels/xianyu/channel.py` 的
 * `deadline = time.monotonic() + timeout`，而 `domains/channel/qr_service.py` 的
 * `_PLATFORM_TIMEOUT["xianyu"] = 120`。也就是说**二维码只有约 120 秒有效期**
 * （`QR_REFRESH_INTERVAL_S = 110`，在 120s 窗口内基本来不及刷新第二次）。
 * 超时后后端还会转一次风控恢复（`_try_risk_recovery`），可能再花几十秒才落到 FAILED。
 *
 * 单条用例的上限由 `wdio.conf.ts` 的 `mochaOpts.timeout`（420s）控制 —— 用例里写
 * `this.timeout()` 在 WDIO 下**不生效**，别在这里写。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { $$, browser, expect } from "@wdio/globals";

import {
  PLATFORM_LABEL,
  countValid,
  describeAccounts,
  fetchAccounts,
  type AccountPlatform,
} from "../helpers/account";
import { waitForPort } from "../helpers/desktop";
import {
  disableAutoFocus,
  dumpContext,
  findButtonByText,
  log as logUi,
  probePage,
  waitForAppShell,
  waitUntil,
} from "../helpers/ui";

const SCOPE = "qr";

const here = path.dirname(fileURLToPath(import.meta.url));
/** 二维码落盘目录：扫码失败时用于事后核对「当时到底显示了什么」。 */
const ARTIFACT_DIR = path.resolve(here, "..", "artifacts");

/** wdio.conf.ts 顶层已把它写入 DINGDA_PORT（同一个值传给被测应用）。 */
const E2E_PORT = Number(process.env.DINGDA_PORT ?? 8799);

/** 需要保证「至少有一个有效账号」的平台。 */
const PLATFORMS: AccountPlatform[] = ["xianyu", "ali1688", "xiaohongshu"];

/** 等二维码出现的上限：含 Camoufox 冷启动 + 登录页加载 + 抓图。 */
const QR_APPEAR_TIMEOUT_MS = 120_000;
/** 等扫码完成的上限：覆盖后端 120s 窗口 + 超时后的风控恢复余量。 */
const SCAN_WAIT_MS = 260_000;
/** 高频轮询的间隔。 */
const POLL_INTERVAL_MS = 1_000;

/**
 * 干跑：只验「进得去账号页、点得到扫码按钮、二维码出得来」，不等扫码。
 *
 * 用于在真正扫码前先确认点击链路通 —— 否则每次失败都要占用你一次 120 秒的扫码窗口。
 *   DINGDA_E2E_QR_DRY_RUN=1 pnpm --filter @v2/e2e exec wdio run wdio.conf.ts --spec ./specs/account-qr.spec.ts
 */
const DRY_RUN = process.env.DINGDA_E2E_QR_DRY_RUN === "1";

/** 后端失败态在弹窗里留下的文案片段（见 xianyu/channel.py 的 raise 处与 http-client 的报错）。 */
const FAILURE_HINTS = ["超时", "已过期", "仍未登录", "无法获取", "失败", "风控"];

/** 需要扫码的平台（在 before 里探测后填充）。 */
const platformsNeedingScan: AccountPlatform[] = [];

function log(message: string): void {
  logUi(SCOPE, message);
}

// ---------------------------------------------------------------------------
// 页面探测（账号页专属；通用部分在 helpers/ui.ts）
// ---------------------------------------------------------------------------

/** 账号页是否已渲染（页签列表的 aria-label 来自 accounts-hub.tsx）。 */
function accountsPageMounted(): Promise<boolean> {
  return browser.execute(() => Boolean(document.querySelector('[aria-label="账号平台"]')));
}

/** 二维码是否已渲染。 */
function qrImagePresent(): Promise<boolean> {
  return browser.execute(() => Boolean(document.querySelector('img[alt="登录二维码"]')));
}

/** 弹窗里是否已出现失败文案；有则返回该文案。 */
async function readDialogFailure(): Promise<string | null> {
  const text = (await probePage()).dialogText;
  if (!text) return null;
  // 「正在自动过滑块…」是风控恢复的**进行中**状态，不是失败。
  if (text.includes("正在") && text.includes("滑块")) return null;
  for (const hint of FAILURE_HINTS) {
    if (text.includes(hint)) return text;
  }
  return null;
}

/** 等二维码出现，期间每 15 秒打印一次弹窗文案（便于看清后端到底给了什么）。 */
async function waitForQrImage(timeoutMs: number): Promise<boolean> {
  const startedAt = Date.now();
  const deadline = startedAt + timeoutMs;
  let lastTick = -1;

  while (Date.now() < deadline) {
    if (await qrImagePresent()) return true;
    const elapsed = Math.round((Date.now() - startedAt) / 1000);
    if (elapsed - lastTick >= 15) {
      lastTick = elapsed;
      log(`等二维码中… ${elapsed}s 弹窗文案：${(await probePage()).dialogText ?? "（无弹窗）"}`);
    }
    await browser.pause(POLL_INTERVAL_MS);
  }
  return false;
}

// ---------------------------------------------------------------------------
// 窗口置前（best-effort）
// ---------------------------------------------------------------------------

/**
 * 尽力把应用窗口提到前台。
 *
 * 为什么需要：`disableAutoFocus()` 关掉了 tauri-service 的自动聚焦，而扫码要求用户
 * **肉眼看到窗口里的二维码**。窗口是被测试进程拉起来的，未必在最前面。
 * tauri-service 没有暴露 OS 级聚焦接口，这里直接调 Tauri 内建的 window 插件命令。
 * 全部 best-effort：任何一步失败都不影响流程，只影响可见性。
 *
 * **现状（实测）**：三条命令都会被拒 —— 壳没开对应 capability：
 *   window.unminimize not allowed. Permissions: core:window:allow-unminimize
 *   window.show       not allowed. Permissions: core:window:allow-show
 *   window.set_focus  not allowed. Permissions: core:window:allow-set-focus
 * 也就是说这一步目前**不起作用**，窗口可见性靠「新窗口被系统置前」这一默认行为。
 * 若哪天发现窗口被压在后面，在 `packages-rs/client/capabilities/*.json` 里放开
 * 上面三条权限即可让这里生效（不建议仅为测试放宽权限，先评估）。
 */
async function raiseWindow(): Promise<void> {
  try {
    const result = await browser.execute(async () => {
      const internals = (
        window as unknown as {
          __TAURI_INTERNALS__?: { invoke?: (cmd: string, args?: unknown) => Promise<unknown> };
        }
      ).__TAURI_INTERNALS__;
      if (!internals?.invoke) return "无 __TAURI_INTERNALS__.invoke";

      const attempts: string[] = [];
      for (const command of [
        "plugin:window|unminimize",
        "plugin:window|show",
        "plugin:window|set_focus",
      ]) {
        try {
          await internals.invoke(command, { label: "main" });
          attempts.push(`${command}=ok`);
        } catch (error) {
          attempts.push(`${command}=${error instanceof Error ? error.message : String(error)}`);
        }
      }
      return attempts.join("; ");
    });
    log(`窗口置前尝试：${result}`);
  } catch (error) {
    console.warn(`[${SCOPE}] 窗口置前失败（不致命）：${String(error)}`);
  }
}

// ---------------------------------------------------------------------------
// 页面操作（真实点击）
// ---------------------------------------------------------------------------

/**
 * 进账号页：点侧栏底部的用户菜单 → 「账号」。
 *
 * 侧栏 `railOpen` 默认 true（entry-layout.tsx），所以进来就能点。
 *
 * 回落说明：侧栏是 base-ui 的下拉（portal + 动画），自动化下偶发点不开。
 * 真点不开时用 hash 回落 —— 应用是 `createHashRouter`（apps/web/src/routes/router.tsx），
 * 改 hash 走的是应用**自己的路由**，不是绕过页面的 HTTP 捷径；扫码本身依然全部点按钮。
 * 这条回落一旦被用到，日志里会明确写出「hash 回落路径」。
 */
async function openAccountsPage(): Promise<void> {
  if (await accountsPageMounted()) return;

  let clickError: unknown = null;
  try {
    const trigger = await findButtonByText("叮答用户");
    if (!trigger) throw new Error("侧栏里找不到用户菜单按钮（文本「叮答用户」）");
    log("点击侧栏用户菜单");
    await trigger.click();

    await browser.pause(400); // 等 portal 里的菜单挂上
    const menuItems = await $$('[data-slot="dropdown-menu-item"]');
    log(`用户菜单展开，项数=${menuItems.length}`);
    let clicked = false;
    for (const item of menuItems) {
      const text = (await item.getText()).trim();
      log(`  菜单项：${text}`);
      if (text === "账号") {
        await item.click();
        clicked = true;
        break;
      }
    }
    if (!clicked) throw new Error("用户菜单里找不到「账号」项");
    log("已点「账号」");
  } catch (error) {
    clickError = error;
    console.warn(`[${SCOPE}] 侧栏点击进账号页失败：${String(error)}`);
  }

  if (await waitUntil(accountsPageMounted, 15_000)) {
    log("账号页已渲染（点击路径）");
    return;
  }

  console.warn(`[${SCOPE}] 侧栏未生效，回落到 hash 路由 #/accounts`);
  await browser.execute(() => {
    window.location.hash = "#/accounts";
  });
  if (await waitUntil(accountsPageMounted, 15_000)) {
    log("账号页已渲染（hash 回落路径）");
    return;
  }

  throw new Error(
    `无法进入账号页（侧栏点击与 hash 回落都失败）\n` +
      `侧栏点击错误：${String(clickError)}\n` +
      `现场快照：${await dumpContext()}`,
  );
}

/** 切到目标平台页签（标签形如「闲鱼账号」）。 */
async function selectPlatformTab(label: string): Promise<void> {
  const wanted = `${label}账号`;
  const triggers = await $$('[data-slot="tabs-trigger"]');
  for (const trigger of triggers) {
    if ((await trigger.getText()).trim() === wanted) {
      await trigger.click();
      await browser.pause(500);
      log(`已切到页签「${wanted}」`);
      return;
    }
  }
  throw new Error(`账号页上找不到「${wanted}」页签\n现场快照：${await dumpContext()}`);
}

/**
 * 找发起扫码的按钮。
 *
 * 两种入口对应两种前置状态，正是本用例要覆盖的：
 *   - 已有但过期的账号 → 卡片上是「重新扫码」（`can_rescan=true`，见
 *     domains/account/session.py 的 `_ACTIONS_XIANYU_EXPIRED`）；
 *   - 一个账号都没有 → 空态与工具栏各有一个「扫码登录」。
 * 优先「重新扫码」，保证过期场景走的是「刷新已有账号登录态」这条真实路径。
 */
async function findScanEntry(): Promise<WebdriverIO.Element> {
  const rescan = await findButtonByText("重新扫码");
  if (rescan) return rescan;
  const login = await findButtonByText("扫码登录");
  if (login) return login;
  throw new Error(
    `账号页上找不到「重新扫码」或「扫码登录」按钮\n现场快照：${await dumpContext()}`,
  );
}

/** 把弹窗里那张二维码导出成 PNG，供事后核对。返回绝对路径。 */
async function dumpQrImage(platform: AccountPlatform): Promise<string | null> {
  const base64 = await browser.execute(async (): Promise<string | null> => {
    const image = document.querySelector<HTMLImageElement>('img[alt="登录二维码"]');
    if (!image?.src) return null;
    // 前端把二维码转成了 blob URL，同源 fetch 即可取回原始字节。
    const response = await fetch(image.src);
    const bytes = new Uint8Array(await response.arrayBuffer());
    let binary = "";
    for (let i = 0; i < bytes.length; i += 1) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  });

  if (!base64) return null;
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const file = path.join(ARTIFACT_DIR, `qr-${platform}-${stamp}.png`);
  fs.writeFileSync(file, Buffer.from(base64, "base64"));
  return file;
}

// ---------------------------------------------------------------------------
// 扫码主流程
// ---------------------------------------------------------------------------

async function runScanFlow(platform: AccountPlatform): Promise<void> {
  const label = PLATFORM_LABEL[platform];
  log(`======== ${label} 扫码流程开始 ========`);

  if (!(await waitForAppShell())) {
    throw new Error(
      `等待应用壳就绪超时（启动屏未消失或主导航未出现）\n现场快照：${await dumpContext()}`,
    );
  }
  log("应用壳已就绪");
  await raiseWindow();

  await openAccountsPage();
  await selectPlatformTab(label);

  const entry = await findScanEntry();
  const entryText = (await entry.getText()).trim();
  log(`点击「${entryText}」`);
  await entry.click();
  log("已点击，等二维码渲染");

  if (!(await waitForQrImage(QR_APPEAR_TIMEOUT_MS))) {
    const failure = await readDialogFailure();
    throw new Error(
      `等待二维码出现超时（${QR_APPEAR_TIMEOUT_MS / 1000}s）` +
        `\n弹窗文案：${failure ?? (await probePage()).dialogText ?? "（无弹窗）"}` +
        `\n现场快照：${await dumpContext()}`,
    );
  }

  const qrFile = await dumpQrImage(platform);
  log(`二维码已显示${qrFile ? `，并已导出：${qrFile}` : ""}`);

  if (DRY_RUN) {
    log("DRY RUN：点击链路已全部验证通过，按开关要求不进入扫码等待。");
    return;
  }

  log(
    `>>> 请用「${label}」App 扫码（应用窗口里那张，或上面导出的图片）。` +
      `后端窗口约 120 秒，请尽快。 <<<`,
  );

  await waitForScanResult(platform);

  const items = await fetchAccounts(E2E_PORT, platform);
  expect(countValid(items, platform)).toBeGreaterThan(0);
  log(`${label} 扫码完成：${describeAccounts(items, platform)}`);
}

/** 阻塞轮询，直到后端落库出有效账号、弹窗报错、或等待超时。 */
async function waitForScanResult(platform: AccountPlatform): Promise<void> {
  const label = PLATFORM_LABEL[platform];
  const startedAt = Date.now();
  const deadline = startedAt + SCAN_WAIT_MS;
  let lastTick = -1;

  while (Date.now() < deadline) {
    // 以服务端落库为准（独立于前端自报）：扫码成功时 /qr/check 会写 auth_valid=True。
    const items = await fetchAccounts(E2E_PORT, platform);
    if (countValid(items, platform) > 0) {
      log("服务端已落库有效账号");
      return;
    }

    // 失败/过期就尽早退出，别让用户干等到上限。
    const failure = await readDialogFailure();
    if (failure) throw new Error(`${label} 扫码失败：${failure}`);

    const elapsed = Math.round((Date.now() - startedAt) / 1000);
    if (elapsed - lastTick >= 15) {
      lastTick = elapsed;
      log(`等待${label}扫码中… 已 ${elapsed}s / ${SCAN_WAIT_MS / 1000}s`);
    }
    await browser.pause(POLL_INTERVAL_MS);
  }

  throw new Error(
    `等待${label}扫码超时（${SCAN_WAIT_MS / 1000}s）。` +
      `当前账号：${describeAccounts(await fetchAccounts(E2E_PORT, platform), platform)}`,
  );
}

// ---------------------------------------------------------------------------
// 用例
// ---------------------------------------------------------------------------

describe("账号扫码流程", () => {
  before(async () => {
    // 壳会自己拉起 Python Server，但 WebDriver session 建好时它可能还没监听上，
    // 所以先等端口，别让 before 直接 ECONNREFUSED 把整组用例带崩。
    if (!(await waitForPort(E2E_PORT, 90_000))) {
      throw new Error(`等待 Python Server 监听 ${E2E_PORT} 超时`);
    }

    // 必须早于任何元素操作：去掉 tauri-service 每个命令 5 秒的自动聚焦开销。
    await disableAutoFocus();

    const items = await fetchAccounts(E2E_PORT);
    for (const platform of PLATFORMS) {
      const label = PLATFORM_LABEL[platform];
      const valid = countValid(items, platform);
      const total = items.filter((item) => item.platform === platform).length;
      if (valid > 0) {
        log(`${label}：已有 ${valid} 个有效账号（共 ${total} 个），无需扫码`);
      } else {
        log(`${label}：${total === 0 ? "无账号" : `${total} 个账号但全部过期`} → 需要扫码`);
        platformsNeedingScan.push(platform);
      }
    }
  });

  it("账号缺失或过期时，走页面扫码并阻塞等待扫码完成", async () => {
    if (platformsNeedingScan.length === 0) {
      log("所有平台账号均有效，无需扫码 —— 本用例不发起任何扫码。");
      return;
    }

    for (const platform of platformsNeedingScan) {
      await runScanFlow(platform);
      if (DRY_RUN) {
        log("DRY RUN 结束：不校验账号（只验点击链路）。");
        return;
      }
    }
  });
});
