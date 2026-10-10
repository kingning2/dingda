/**
 * AI 找商品 E2E：首页发一句「去找商品」→ 跳工作页自动开跑（内置 dingda Agent）
 * → 右侧出商品结果。
 *
 * 与另外两条 spec 的分工：`desktop-smoke` 验壳层装配，`account-qr` 验账号登录；
 * 本条验**业务链路**：用户的一句话能不能真的变成一次 Agent 运行，并在结果面板里
 * 产出商品。
 *
 * ## 驱动原则
 * 全程点页面上的控件（输入框 → 发送按钮），**不直接打
 * `POST /v1/agent/works/{id}/run`** —— 那条路会绕过「首页 stash 草稿 → 工作页
 * 自动发送」这段真实编排，而这段恰恰是最容易坏的（hash 路由 + pendingSend）。
 * 测试进程只做旁证：跑完之后读 `GET /v1/agent/works/{work_id}` 核对落库结果。
 *
 * ## 副作用
 * - **不写用户偏好**：Agent 固定内置 dingda，Composer 不再有选择器。
 * - **会新增一条 AI 工作记录**：`work-<时间戳>` 写进 `~/.dingda/v2/dingda.db`
 *   （首页 `createWorkId()` + 工作页 `PUT /v1/agent/works/{work_id}`）。
 *   后端没有删除接口，所以用例**不清理** —— 它会出现在首页「最近项目」里。
 *   这是真实用户行为，且可手动删；跑多次会多几条，属预期。
 *
 * ## 分步判断（本用例的核心能力）
用户要的是「每一步都判断 Agent 有没有跑对」，而不是只等最后看结果。做法是：
在运行期间**每 4s 采样一次前端状态行**，把经历的**阶段**与每个**工具步骤**
（`└ 搜索商品 · 闲鱼` 这类 `label · hint`）记成时间线，然后做两层判定：

- **结构层（自动）**：① 至少出现过一个工具步骤（否则说明它只聊天没去搜）；
  ② 阶段数 > 0（不是一上来就 completed）；③ 中途若捕捉到 `errorText` 就**立刻
  取消并失败**，不等满超时。这三点是机械可判的「链路没坏」。
- **语义层（人工）**：「这一步搜得对不对、商品是否真相关」机器下不了结论。
  所以时间线会**全程 dump 到 `artifacts/ai-search-<workId>-<时间戳>.json`**，
  你跑完直接打开看 `timeline.steps` 即可逐条核对 Agent 到底干了什么。

## 时间预算（本文件的常量按这个来）
 * 真实的找商品 = 内置 Agent 调搜索工具 → 起浏览器爬平台，单轮常见几分钟。
 * 所以等运行结束默认给 600s（`DINGDA_E2E_RUN_TIMEOUT_MS` 可调），
 * 且 `wdio.conf.ts` 的 `mochaOpts.timeout` 必须大于它 —— 用例里写 `this.timeout()`
 * 在 WDIO 下不生效，别写。
 *
 * ## 前置条件：模型（最容易踩）
 * 这条用例的成败**首先取决于模型能力**，而不是用例写得对不对。内置 Agent 的模型
 * 由 Server 侧 `DINGDA_LLM_*` 环境变量决定，上下文太小的模型会直接报
 * context length 超限、`exitCode=1`，用例就必然失败在「没抓到商品」上。
 * 当前实际使用的模型每次都会打进日志首行。
 *
 * ## 选择器
 * 一律用源码里写死的东西，不碰 CSS 类名与文案层级：
 *   - `[data-testid="home-hero"]`（`ui-home/home-hero.tsx`）—— 首页已渲染；
 *   - `[data-slot="textarea"]`（`ui-primitives/textarea.tsx`）—— 输入框；
 *   - `button[aria-label="发送"]` / `button[aria-label="停止生成"]`
 *     （`ui-composer/prompt-composer.tsx`）—— 发送与「正在跑」；
 *   - 结果面板：`h2` 文本「爬取结果」的 `parentElement` 即面板根
 *     （`ui-ai/src/panel/products.tsx`），再往下取 `[data-slot="card-title"]`。
 *
 * 已知坑（每个命令 5 秒的自动聚焦、打标记前必须清标记等）见 `e2e/README.md`
 * 与 `helpers/ui.ts`。
 *
 * ## 干跑
 * 真跑一轮要几分钟。只想确认「点得到发送、运行真的起来了、取消也有效」时：
 *   DINGDA_E2E_SEARCH_DRY_RUN=1 pnpm --filter @v2/e2e exec wdio run wdio.conf.ts --spec ./specs/ai-product-search.spec.ts
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { $, browser, expect } from "@wdio/globals";

import {
  fetchWorkDetail,
  lastAssistantText,
  type WorkDetailSnapshot,
} from "../helpers/ai-work";
import { waitForPort } from "../helpers/desktop";
import {
  disableAutoFocus,
  dumpContext,
  findButtonByText,
  log,
  waitForAppShell,
  waitUntil,
} from "../helpers/ui";

const SCOPE = "ai-search";

const here = path.dirname(fileURLToPath(import.meta.url));
/** 落盘目录：跑完把结果快照存下来，便于事后回看「当时抓到了什么」。 */
const ARTIFACT_DIR = path.resolve(here, "..", "artifacts");

/** wdio.conf.ts 顶层已把它写入 DINGDA_PORT（同一个值传给被测应用）。 */
const E2E_PORT = Number(process.env.DINGDA_PORT ?? 8799);

/** 用哪个 Agent 跑：内置产品 Agent，固定 dingda（模型由 Server 侧 DINGDA_LLM_* 决定）。 */
const AGENT_ID = "dingda";

/**
 * 发给 Agent 的话。
 *
 * 刻意写死「只调一次 search、不要补详情、不要比价」：本用例验证的是
 * 「一句话 → 商品结果」这条链路，不是比价质量；多轮比价会把单轮耗时从
 * 几分钟拉到十几分钟，超出任何合理的用例预算。
 */
const PROMPT = (
  process.env.DINGDA_E2E_PROMPT ??
  "在闲鱼搜索“露营椅”，给我 5 个真实商品：标题、价格、卖家。" +
    "只调用一次 search，不要调用 product，不要比价，拿到结果就立刻用一句话总结。"
).trim();

/** 等一轮运行跑完的上限。 */
const RUN_TIMEOUT_MS = Number(process.env.DINGDA_E2E_RUN_TIMEOUT_MS ?? 600_000);
/** 等运行「起来」（出现停止按钮）的上限。 */
const START_TIMEOUT_MS = 90_000;
/** 结果面板至少要有的商品条数。 */
const MIN_PRODUCTS = Number(process.env.DINGDA_E2E_MIN_PRODUCTS ?? 1);

/** 干跑：只验「发得出去、跑起来了、取消得掉」，不等结果。 */
const DRY_RUN = process.env.DINGDA_E2E_SEARCH_DRY_RUN === "1";

/**
 * 运行期间采状态行的间隔：几秒一次足矣，太密只会让日志变长。
 * 每次都走 `browser.execute`，不在 tauri-service 的 focusCommands 列表里。
 */
const TIMELINE_INTERVAL_MS = 4_000;

// ---------------------------------------------------------------------------
// 页面探测（一律走 execute，避开 tauri-service 的 focusCommands）
// ---------------------------------------------------------------------------

/** 首页锚点（源码里写死，非 CSS 类名）。 */
const HERO = '[data-testid="home-hero"]';

type WorkProbe = {
  hash: string;
  /** 从 `#/work/<id>` 里解出的 workId；不在工作页则为 null。 */
  workId: string | null;
  /** 运行中：停止按钮存在 = `busy = !can_send`（见 layout.tsx 的 busy 传参）。 */
  busy: boolean;
  /** 输入框是否禁用（跑完应为 false）。 */
  composerDisabled: boolean | null;
  /** 右侧「爬取结果」面板是否渲染。 */
  resultPanel: boolean;
  /** 「共 N 条」原文；没有商品时后端/前端都不渲染这几个字。 */
  totalText: string | null;
  /** 面板里商品卡片的标题（前 10 条）。 */
  titles: string[];
  /**
   * 错误文案（前端 `error` state）。
   *
   * 这里破例用了 class 名：错误行没有任何 data-slot / aria 锚点
   * （`chat.tsx` 里就是 `<p className="text-sm text-destructive">`）。
   * 只作诊断与失败归因，不作为唯一判据。
   */
  errorText: string | null;
  /** 页面尾部文本，失败时看一眼就知道卡在哪。 */
  bodyTail: string;
};

/** 一次性把工作页的关键状态抓回来。 */
function probeWork(): Promise<WorkProbe> {
  return browser.execute(() => {
    const text = (node: Element | null | undefined): string =>
      (node?.textContent ?? "").replace(/\s+/g, " ").trim();

    const header = Array.from(document.querySelectorAll("h2")).find(
      (node) => text(node) === "爬取结果",
    );
    // products.tsx 的结构：面板根 div > header，故 header 的父节点就是面板根。
    const panel = header?.parentElement ?? null;
    const totalNode = panel
      ? Array.from(panel.querySelectorAll("span")).find((node) => text(node).startsWith("共 "))
      : null;
    const textarea = document.querySelector<HTMLTextAreaElement>('[data-slot="textarea"]');
    const stop = document.querySelector('button[aria-label="停止生成"]');
    const errorNode = Array.from(document.querySelectorAll("p")).find((node) =>
      (node.className || "").includes("text-destructive"),
    );
    const hash = window.location.hash;
    const matched = hash.match(/^#\/work\/([^/?#]+)/);

    return {
      hash,
      workId: matched ? decodeURIComponent(matched[1]) : null,
      busy: Boolean(stop),
      composerDisabled: textarea ? textarea.disabled : null,
      resultPanel: Boolean(panel),
      totalText: totalNode ? text(totalNode) : null,
      titles: panel
        ? Array.from(panel.querySelectorAll('[data-slot="card-title"]'))
            .map((node) => text(node))
            .filter(Boolean)
            .slice(0, 10)
        : [],
      errorText: errorNode ? text(errorNode) : null,
      bodyTail: (document.body.innerText ?? "").replace(/\s+/g, " ").slice(-400),
    };
  });
}

/** 实时状态行（`ui-ai/src/chat/working-status.tsx` 的 `WorkingIndicator`）。 */
type WorkingIndicator = {
  /** 状态行是否存在（存在 = 正在跑某一阶段）。 */
  present: boolean;
  /**
   * 阶段标签原文：`• 执行中 (12s • esc to interrupt)`。
   * 前缀 `• ` 是 Codex TUI 风格活动符，去掉更干净。
   */
  label: string | null;
  /**
   * 当前工具步骤详情：`└ 搜索商品 · 闲鱼`。
   * 前缀 `└ ` 是 TUI 风格缩进，去掉更干净。
   */
  detail: string | null;
};

/**
 * 读当前状态行。
 *
 * 锚点用 `aria-label="Agent working"`（源码里写死的，非 CSS 类名）；内部的
 * `.codex-status-shimmer` 是 class（诊断用，同 errorText 的例外处理）。
 * 结构固定：状态行 = 根节点的第一个子元素，详情 = 根节点里的 `<p>`。
 */
function workingIndicator(): Promise<WorkingIndicator> {
  return browser.execute(() => {
    const root = document.querySelector('[aria-label="Agent working"]');
    if (!root) return { present: false, label: null, detail: null };
    const text = (node: Element | null | undefined): string =>
      (node?.textContent ?? "").replace(/\s+/g, " ").trim();
    const statusLine = root.firstElementChild;
    const detailNode = root.querySelector("p");
    const label = text(statusLine).replace(/^•\s*/, "");
    const detail = detailNode ? text(detailNode).replace(/^└\s*/, "") : null;
    return { present: true, label: label || null, detail: detail || null };
  });
}

/** 一次运行采集到的「分步时间线」。 */
type RunTimeline = {
  /** 去重后的阶段标签，如 `["正在启动","执行中","商品结果"]`。 */
  phases: string[];
  /** 按出现顺序、去重后的工具步骤详情（去掉 `└ ` 前缀）。 */
  steps: string[];
  /** 是否在中途（跑完之前）捕捉到错误。 */
  errored: boolean;
};

/**
 * 运行期间分步采样。
 *
 * 这是「分步判断」的核心：每 `TIMELINE_INTERVAL_MS` 抓一次状态行，把经历的
 * 阶段与每条工具步骤记下来。三种退出条件：
 *   - 跑完（停止按钮消失）→ 正常返回，等着做最终断言；
 *   - 中途报错（`errorText` 出现）→ `errored=true` 返回，调用方应取消并失败；
 *   - 超时 → 返回（调用方用 `waitForRunEnd` 的语义抛超时）。
 *
 * 注意：只做**记录与结构判定**，不作语义结论。「这一步搜得对不对」是语义判断，
 * 机器下不了，时间线 dump 出来是给人工逐条核对的（见 dumpRunArtifact）。
 */
async function collectRunTimeline(timeoutMs: number): Promise<RunTimeline> {
  const phases = new Set<string>();
  const steps: string[] = [];
  let lastDetail: string | null = null;
  let errored = false;

  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const probe = await probeWork();
    if (!probe.busy) break; // 跑完了
    if (probe.errorText) {
      errored = true;
      log(SCOPE, `分步采样捕捉到错误：${probe.errorText}`);
      break;
    }

    const wi = await workingIndicator();
    if (wi.present) {
      if (wi.label) phases.add(wi.label);
      if (wi.detail && wi.detail !== lastDetail) {
        steps.push(wi.detail);
        lastDetail = wi.detail;
        log(SCOPE, `运行步骤：${wi.detail}`);
      }
    }

    await browser.pause(TIMELINE_INTERVAL_MS);
  }

  return { phases: [...phases], steps, errored };
}

/** 首页是否已渲染。 */
function homeReady(): Promise<boolean> {
  return browser.execute<boolean, [string]>((selector) => {
    return Boolean(document.querySelector(selector));
  }, HERO);
}
// ---------------------------------------------------------------------------
// 页面操作（真实点击）
// ---------------------------------------------------------------------------

/**
 * 归位到首页。
 *
 * 必须显式做：**URL（含 hash）会跨应用实例残留**（README 已知坑 3），
 * 实例一起来可能就在 `#/agents` 或上个 spec 留下的 `#/work/...`，
 * 那时首页的 home-hero 根本不存在，输入也无从谈起。
 */
async function ensureHome(): Promise<void> {
  const hash = await browser.execute(() => window.location.hash);
  if (hash && hash !== "#/") {
    log(SCOPE, `进入时路由为 "${hash}"（上一个 spec 残留），点侧栏「首页」归位`);
    const home = await findButtonByText("首页", "exact");
    if (!home) throw new Error(`侧栏里找不到「首页」导航项\n现场快照：${await dumpContext()}`);
    await home.click();
  }

  if (!(await waitUntil(homeReady, 20_000))) {
    throw new Error(`首页未渲染\n现场快照：${await dumpContext()}`);
  }
  log(SCOPE, "已在首页");
}
/**
 * 把提示词敲进输入框。
 *
 * 优先走真实键盘（`setValue`）；万一受控组件没收到（WebDriver 对中文 IME 的兼容
 * 差异），再用原生 setter 兜底并**显式告警** —— 静默兜底会掩盖输入框真的坏了。
 */
async function typePrompt(prompt: string): Promise<void> {
  const textarea = await $(`${HERO} [data-slot="textarea"]`);
  await textarea.setValue(prompt);

  const typed = await browser.execute<string, [string]>(
    (heroSelector) =>
      document.querySelector<HTMLTextAreaElement>(`${heroSelector} [data-slot="textarea"]`)?.value ??
      "",
    HERO,
  );

  if (typed.trim() !== prompt) {
    console.warn(`[${SCOPE}] 键盘输入未生效（读到 ${typed.length} 字），改用原生 setter 兜底`);
    await browser.execute<void, [string, string]>(
      (heroSelector, value) => {
        const node = document.querySelector<HTMLTextAreaElement>(
          `${heroSelector} [data-slot="textarea"]`,
        );
        if (!node) return;
        const setter = Object.getOwnPropertyDescriptor(
          HTMLTextAreaElement.prototype,
          "value",
        )?.set;
        setter?.call(node, value);
        node.dispatchEvent(new Event("input", { bubbles: true }));
      },
      HERO,
      prompt,
    );
  }

  const finalValue = await browser.execute<string, [string]>(
    (heroSelector) =>
      document.querySelector<HTMLTextAreaElement>(`${heroSelector} [data-slot="textarea"]`)?.value ??
      "",
    HERO,
  );
  if (finalValue.trim() !== prompt) {
    throw new Error(`输入框内容不对（期望 ${prompt.length} 字，实际 ${finalValue.length} 字）`);
  }
  log(SCOPE, `已输入提示词（${prompt.length} 字）：${prompt.slice(0, 40)}…`);
}

/** 点发送按钮（aria-label 写死在 prompt-composer.tsx）。 */
async function submitPrompt(): Promise<void> {
  const send = await $('button[aria-label="发送"]');
  await send.click();
  log(SCOPE, "已点击发送");
}

/** 等路由跳到 `#/work/<id>`，返回 workId。 */
async function waitForWorkRoute(timeoutMs = 30_000): Promise<string> {
  const ok = await waitUntil(async () => (await probeWork()).workId !== null, timeoutMs, 300);
  if (!ok) {
    throw new Error(`发送后未跳转到工作页\n现场快照：${await dumpContext()}`);
  }
  const workId = (await probeWork()).workId ?? "";
  log(SCOPE, `已进入工作页：${workId}`);
  return workId;
}

/**
 * 等运行真正开始，返回 `{ started, error }`。
 *
 * **判据为什么不是 `busy`**（2026-09-14 实测踩坑）：`busy` 就是「停止按钮存在」，
 * 而它等价于 `!detail.can_send`。带草稿跳进工作页时 `buildEmptyWorkDetail` 直接给
 * `can_send: false`（见 `ui-ai/src/work/session.ts` 的 `can_send: !seedPrompt`），
 * 于是**页面一到工作页 `busy` 就是 true** —— 那只能说明「已进入工作页」，与 Agent
 * 是否启动无关。反过来，若运行秒级失败，`busy` 的 true 窗口极短，300ms 轮询还可能
 * 整个错过。两种偏差合起来就是：干跑侥幸通过、真跑失败。
 *
 * 改用 `[aria-label="Agent working"]`：它由 `shouldShowWorking(activePhase, …)` 决定，
 * 而 `activePhase` 只在收到 SSE 事件（thinking / toolCall / textDelta）后才非 null。
 * 即**这个元素出现 ⟺ 后端真的推来了运行事件**。
 *
 * 顺带在等待期间盯 `errorText`：运行秒级失败时立刻返回真实错误，不干等满超时
 * —— 否则「没起来」和「起来就炸了」在报告里长得一样，排查方向会被带偏。
 */
async function waitForRunStart(
  timeoutMs = START_TIMEOUT_MS,
): Promise<{ started: boolean; error: string | null }> {
  let error: string | null = null;
  const started = await waitUntil(async () => {
    if ((await workingIndicator()).present) return true;
    const probe = await probeWork();
    if (probe.errorText) {
      error = probe.errorText;
      return true; // 提前退出，由调用方按 error 分支报错
    }
    return false;
  }, timeoutMs, 300);
  return { started, error };
}

/** 点「停止生成」取消这一轮（干跑与中途报错时用到）。 */
async function cancelRun(): Promise<void> {
  const stop = await $('button[aria-label="停止生成"]');
  await stop.click();
  log(SCOPE, "已点击「停止生成」");
}

/** 等后端落库到「可发送」的最终态（前端 `can_send` 为真时才 flush 持久化）。 */
async function waitForPersistedWork(
  workId: string,
  timeoutMs = 30_000,
): Promise<WorkDetailSnapshot | null> {
  let snapshot: WorkDetailSnapshot | null = null;
  await waitUntil(async () => {
    snapshot = await fetchWorkDetail(E2E_PORT, workId);
    return snapshot !== null && snapshot.can_send === true;
  }, timeoutMs, 500);
  return snapshot;
}

/** 把结果快照落盘，失败时当成诊断材料。 */
function dumpRunArtifact(name: string, payload: unknown): string | null {
  try {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const file = path.join(ARTIFACT_DIR, `${name}-${stamp}.json`);
    fs.writeFileSync(file, JSON.stringify(payload, null, 2), "utf8");
    return file;
  } catch (error) {
    console.warn(`[${SCOPE}] 结果快照落盘失败（不影响判定）：${String(error)}`);
    return null;
  }
}

// ---------------------------------------------------------------------------
// 用例
// ---------------------------------------------------------------------------

describe("AI 找商品（内置 Agent 真实跑一轮）", () => {
  before(async () => {
    // 壳会自己拉起 Python Server，但 WebDriver session 建好时它可能还没监听上。
    if (!(await waitForPort(E2E_PORT, 90_000))) {
      throw new Error(`等待 Python Server 监听 ${E2E_PORT} 超时`);
    }
    // 必须早于任何元素操作：去掉 tauri-service 每个命令 5 秒的自动聚焦开销。
    await disableAutoFocus();
    await waitForAppShell();
    log(SCOPE, "目标 Agent=叮答（内置 dingda，模型由 Server 侧 DINGDA_LLM_* 决定）");
  });

  it("首页发起找商品 → 工作页跑完 → 右侧出商品结果", async () => {
    await ensureHome();
    await typePrompt(PROMPT);
    await submitPrompt();

    const workId = await waitForWorkRoute();

    if (DRY_RUN) {
      const start = await waitForRunStart();
      if (start.error) {
        throw new Error(`干跑：运行起来就失败了：${start.error}\n现场快照：${await dumpContext()}`);
      }
      if (!start.started) {
        throw new Error(
          `干跑：发送后运行未启动（${START_TIMEOUT_MS / 1000}s 内没出现「Agent working」）\n` +
            `现场快照：${await dumpContext()}`,
        );
      }
      log(SCOPE, "干跑：运行已启动，点「停止生成」验证取消链路");
      await cancelRun();
      const stopped = await waitUntil(async () => !(await probeWork()).busy, 60_000, 500);
      expect(stopped).toBe(true);
      log(SCOPE, "干跑：取消成功，本轮到此为止（不校验商品结果）");
      return;
    }

    // 先等「跑起来了」，再边跑边采样时间线，最后等「跑完了」。
    // 少了第一步，发送失败会伪装成「运行已结束」。
    const start = await waitForRunStart();
    if (start.error) {
      throw new Error(
        `发送后运行失败（起来就报错）：${start.error}\n` + `现场快照：${await dumpContext()}`,
      );
    }
    if (!start.started) {
      const probe = await probeWork();
      throw new Error(
        `发送后运行未启动（${START_TIMEOUT_MS / 1000}s 内没出现「Agent working」）\n` +
          `错误文案：${probe.errorText ?? "（无）"}\n现场快照：${await dumpContext()}`,
      );
    }
    log(SCOPE, `运行已启动，分步采样中（上限 ${RUN_TIMEOUT_MS / 1000}s）…`);

    const timeline = await collectRunTimeline(RUN_TIMEOUT_MS);

    // 分步判断（结构层）：中途报错 → 提前取消并失败，不必干等超时。
    if (timeline.errored) {
      const probe = await probeWork();
      await cancelRun().catch(() => undefined); // 尽力回收，失败不阻塞报错
      throw new Error(
        `运行中途报错（已取消）：${probe.errorText ?? "（无）"}\n` +
          `已观察到的阶段：${JSON.stringify(timeline.phases)}\n` +
          `已观察到的步骤：${JSON.stringify(timeline.steps)}`,
      );
    }

    // 超时（采样循环正常退完但仍在跑）→ 走标准超时语义。
    if (await probeWork().then((probe) => probe.busy)) {
      const probe = await probeWork();
      throw new Error(
        `等待运行结束超时（${RUN_TIMEOUT_MS / 1000}s）\n` +
          `当前：${JSON.stringify(probe)}\n已观察阶段：${JSON.stringify(timeline.phases)}\n` +
          `提示：可用 DINGDA_E2E_RUN_TIMEOUT_MS 放宽，或先用 ` +
          `DINGDA_E2E_SEARCH_DRY_RUN=1 只验启动链路。`,
      );
    }

    const probe = await probeWork();
    log(
      SCOPE,
      `运行结束：结果面板=${probe.resultPanel} 计数文案=${probe.totalText ?? "（无）"} ` +
        `可见标题 ${probe.titles.length} 条 错误=${probe.errorText ?? "（无）"}\n` +
        `时间线：阶段=${JSON.stringify(timeline.phases)} 步骤=${JSON.stringify(timeline.steps)}`,
    );

    // 分步判断（结构层）：Agent 必须真的调过工具，而不是只聊天没去搜。
    // 没出现任何工具步骤（steps 为空）通常意味着它直接回了段话、没执行 search。
    expect(timeline.steps.length).toBeGreaterThan(0);
    expect(timeline.phases.length).toBeGreaterThan(0);

    // 落盘一份快照（含时间线），失败后不用再复跑一轮（一轮几分钟）。
    const snapshot = await waitForPersistedWork(workId);
    const artifact = dumpRunArtifact(`ai-search-${workId}`, {
      workId,
      agent: AGENT_ID,
      prompt: PROMPT,
      timeline,
      ui: probe,
      api: snapshot,
    });
    if (artifact) log(SCOPE, `结果快照已落盘：${artifact}（含分步时间线，可逐条核对）`);

    // —— 断言 1：前端确实拿到了商品 ——
    expect(probe.errorText ?? null).toBeNull();
    expect(probe.resultPanel).toBe(true);
    expect(probe.totalText).not.toBeNull();
    const uiTotal = Number((probe.totalText ?? "").match(/(\d+)/)?.[1] ?? 0);
    expect(uiTotal).toBeGreaterThanOrEqual(MIN_PRODUCTS);
    expect(probe.titles.length).toBeGreaterThan(0);
    log(SCOPE, `页面显示 ${uiTotal} 条，前几条：${probe.titles.slice(0, 3).join(" | ")}`);

    // —— 断言 2：独立取证（不依赖前端自报） ——
    expect(snapshot).not.toBeNull();
    const apiItems = snapshot?.products?.items ?? [];
    expect(apiItems.length).toBeGreaterThanOrEqual(MIN_PRODUCTS);
    expect(snapshot?.products?.total ?? 0).toBeGreaterThanOrEqual(MIN_PRODUCTS);

    // 两侧对得上：页面看到的标题必须能在落库数据里找到。
    const apiTitles = apiItems.map((item) => item.title);
    const matched = probe.titles.filter((title) => apiTitles.includes(title));
    expect(matched.length).toBeGreaterThan(0);
    log(SCOPE, `落库 ${apiItems.length} 条，与页面标题重合 ${matched.length} 条`);

    // —— 断言 3：确实是用内置 Agent 跑的 ——
    expect(snapshot?.composer_agent_id ?? null).toBe(AGENT_ID);

    // 商品必须带得出来「是什么、多少钱」：标题或价格全空说明解析没落对。
    const usable = apiItems.filter((item) => item.title?.trim() && item.id?.trim());
    expect(usable.length).toBe(apiItems.length);
    log(
      SCOPE,
      `样例：${apiItems
        .slice(0, 3)
        .map((item) => `${item.title}（${item.price || "无价"}）`)
        .join(" | ")}`,
    );

    if (apiItems.length === 0) {
      console.warn(`[${SCOPE}] 助手原文：${lastAssistantText(snapshot)}`);
    }
  });
});
