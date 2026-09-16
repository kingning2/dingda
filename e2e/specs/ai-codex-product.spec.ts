/**
 * Codex 找商品 E2E：首页选 Codex → 发一句「去闲鱼找商品」→ 工作页跑完 → 出商品 + 出直播流。
 *
 * 职责：
 *   钉死 Codex 这条业务链路能不能端到端跑通：拿得到商品、页面上出现过浏览器直播流、
 *   步骤块能折叠且能看到命令行与完整原始输出、且**思考过程与回复正文都是中文**。
 *   与 `ai-product-search` 分工：那条默认跑 opencode，本条固定 Codex
 *   （可用 `DINGDA_E2E_AGENT_ID` 覆盖）。
 *
 * 驱动原则：全程点页面控件，不直打 `/v1/agent/runtimes/{id}/run`。
 * 测试进程只做旁证：跑完读 `GET /v1/agent/works/{work_id}`。
 *
 * 设计说明：
 *   - 直播流三重取证：运行中采样（LIVE 徽标 / data:image 截图）→ 跑完补采 →
 *     落库 `browser_history` 里有 `screenshot_url` 的帧。三者任一成立即算通过，
 *     因为直播帧只在抓取窗口内推，采样错过是常态而非故障。
 *   - 步骤块断言走源码里写死的 `data-testid`（`step-block` / `step-terminal-*`），
 *     不碰 CSS 类名。收起时正文被卸载，所以命令行与输出必须先真实点开再读。
 *   - 中文判据只看**思考块与助手正文**（用户真正读到的部分）：工具命令、URL、
 *     平台 id 允许保留英文，故只对「连续英文长段」与「汉字数」做宽松断言。
 *
 * 干跑（只验能选中、能开跑、能取消）：
 *   DINGDA_E2E_CODEX_DRY_RUN=1 pnpm e2e:codex
 *
 * 模型：默认用 Codex 目录里的 preferred_model_id；本机若走自定义代理，
 * 可设 DINGDA_E2E_MODEL_ID=deepseek-v4-flash（否则会打到未鉴权的 api.openai.com）。
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
import { fetchAgentRuntimes, type AgentRuntimeItem } from "../helpers/agent";
import { waitForPort } from "../helpers/desktop";
import {
  disableAutoFocus,
  dumpContext,
  findButtonByText,
  log,
  waitForAppShell,
  waitUntil,
} from "../helpers/ui";

const SCOPE = "codex-product";

/** 默认 Codex；本机没装时可临时换成 opencode 复跑同一条链路。 */
const AGENT_ID = (process.env.DINGDA_E2E_AGENT_ID ?? "codex").trim();

const here = path.dirname(fileURLToPath(import.meta.url));
const ARTIFACT_DIR = path.resolve(here, "..", "artifacts");

/** wdio.conf.ts 顶层已把它写入 DINGDA_PORT（同一个值传给被测应用）。 */
const E2E_PORT = Number(process.env.DINGDA_PORT ?? 8799);
const MODEL_ID = process.env.DINGDA_E2E_MODEL_ID?.trim() || null;
const DRY_RUN = process.env.DINGDA_E2E_CODEX_DRY_RUN === "1";
/**
 * 一轮完整选品的上限。
 *
 * 完整链路 = 小红书看风向 + 闲鱼核供给两次 search，每次都要起浏览器爬平台
 * （skill 文档写明单次 1~5 分钟），再叠多轮工具与长思考，实测常见 8~15 分钟。
 * 所以默认给 900s，且 `wdio.conf.ts` 的 `mochaOpts.timeout` 必须大于它。
 */
const RUN_TIMEOUT_MS = Number(process.env.DINGDA_E2E_RUN_TIMEOUT_MS ?? 900_000);
const START_TIMEOUT_MS = 90_000;
const MIN_PRODUCTS = Number(process.env.DINGDA_E2E_MIN_PRODUCTS ?? 1);
/** 运行期采样间隔。 */
const TIMELINE_INTERVAL_MS = 4_000;

/** 首页锚点（源码里写死，非 CSS 类名）。 */
const HERO = '[data-testid="home-hero"]';

/** 临时标记（每个用途一个属性名，每次打之前先清）。 */
const AGENT_TRIGGER_ATTR = "data-e2e-agent-trigger";
const AGENT_SUB_ATTR = "data-e2e-agent-sub";
const AGENT_MODEL_ATTR = "data-e2e-agent-model";
const THOUGHT_ATTR = "data-e2e-thought";
const STEP_SUMMARY_ATTR = "data-e2e-step-summary";

/**
 * 发给 Agent 的话：**搜索 → 打开详情**两步，都走浏览器。
 *
 * 为什么要显式要求「打开详情」：只跑 search 的话 Agent 拿列表就收工，详情页那条
 * 链路（含详情阶段的直播帧）永远验不到 —— 用户最初报的「进详情没有直播」正是这里。
 *
 * 为什么要把「不许中途放弃」写进提示词：本机模型（deepseek-v4-flash）在长命令上
 * 会自己提前收尾，实测表现为搜索跑到 1~2 分钟时会话就结束了，结果面板恒为 0 条。
 * 这不是链路坏了，是模型没等命令返回。
 */
const PROMPT = (
  process.env.DINGDA_E2E_PROMPT ??
  "在闲鱼搜索「露营椅」，给我 3 个真实商品（标题、价格、卖家）。" +
    "拿到搜索结果后，**必须再打开其中 1 个商品的详情页**看真实价格与卖家，再给结论。" +
    "硬性要求：每条命令都必须等它真正返回完整结果再继续；" +
    "命令还在跑就继续轮询等待，**绝不允许中途提前结束或放弃**（单次要 1~5 分钟属正常）。" +
    "思考过程与最终回答都必须用中文。"
).trim();

// ---------------------------------------------------------------------------
// 页面探测（一律走 execute，避开 tauri-service 的 focusCommands）
// ---------------------------------------------------------------------------

type WorkProbe = {
  /** 从 `#/work/<id>` 解出的 workId；不在工作页则为 null。 */
  workId: string | null;
  /** 运行中：停止按钮存在。 */
  busy: boolean;
  /** 右侧「爬取结果」面板是否渲染。 */
  resultPanel: boolean;
  /** 「共 N 条」原文。 */
  totalText: string | null;
  /** 面板里商品卡片标题（前 10 条）。 */
  titles: string[];
  /** 前端 error state（无 data-slot 锚点，破例用 class 名，仅作归因）。 */
  errorText: string | null;
  /** 页面尾部文本，失败时一眼看出卡在哪。 */
  bodyTail: string;
};

/** 一次性把工作页关键状态抓回来。 */
function probeWork(): Promise<WorkProbe> {
  return browser.execute(() => {
    const text = (node: Element | null | undefined): string =>
      (node?.textContent ?? "").replace(/\s+/g, " ").trim();
    const titleNode = Array.from(document.querySelectorAll("h2")).find(
      (node) => text(node) === "爬取结果",
    );
    // products.tsx 是「面板根 div > header > div.min-w-0 > h2」：直接取 h2 的父节点
    // 只拿到那层 min-w-0 → 面板看起来是空的（假阴性）。必须先 closest("header")。
    const panel = titleNode?.closest("header")?.parentElement ?? titleNode?.parentElement ?? null;
    const totalNode = panel
      ? Array.from(panel.querySelectorAll("span")).find((node) => text(node).startsWith("共 "))
      : null;
    const stop = document.querySelector('button[aria-label="停止生成"]');
    const errorNode = Array.from(document.querySelectorAll("p")).find((node) =>
      (node.className || "").includes("text-destructive"),
    );
    const matched = window.location.hash.match(/^#\/work\/([^/?#]+)/);
    return {
      workId: matched ? decodeURIComponent(matched[1]) : null,
      busy: Boolean(stop),
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

/** 实时状态行（`ui-ai/src/chat/working-status.tsx`）。 */
type WorkingIndicator = {
  present: boolean;
  /** 阶段标签：`执行中 (12s • esc to interrupt)`。 */
  label: string | null;
  /** 当前工具步骤：`└ 搜索商品 · 闲鱼`。 */
  detail: string | null;
};

/**
 * 读状态行。
 *
 * 判据为什么是它：`busy`（停止按钮）等价于 `!can_send`，带草稿进工作页时一进去就是
 * true，只能说明「到了工作页」；而 `aria-label="Agent working"` 只在收到 SSE 运行
 * 事件后才出现 —— 它出现 ⟺ 后端真的在跑。
 */
function workingIndicator(): Promise<WorkingIndicator> {
  return browser.execute(() => {
    const root = document.querySelector('[aria-label="Agent working"]');
    if (!root) return { present: false, label: null, detail: null };
    const text = (node: Element | null | undefined): string =>
      (node?.textContent ?? "").replace(/\s+/g, " ").trim();
    const label = text(root.firstElementChild).replace(/^•\s*/, "");
    const detailNode = root.querySelector("p");
    const detail = detailNode ? text(detailNode).replace(/^└\s*/, "") : null;
    return { present: true, label: label || null, detail: detail || null };
  });
}

/** 直播流痕迹：LIVE 徽标 / 「直播中」文案 / data:image 截图（后端 live-frame 推上来的）。 */
function probeLiveStream(): Promise<{ live: boolean; sample: string | null }> {
  return browser.execute(() => {
    const body = (document.body.innerText ?? "").replace(/\s+/g, " ");
    const hasLiveWord = body.includes("直播中") || body.includes("LIVE");
    const shot = Array.from(document.querySelectorAll("img")).find((img) =>
      (img.getAttribute("src") ?? "").startsWith("data:image"),
    );
    const liveBadge = Array.from(document.querySelectorAll("span, div")).some(
      (node) => (node.textContent ?? "").trim() === "LIVE",
    );
    const hasShot = Boolean(shot);
    const live = liveBadge || (hasLiveWord && hasShot) || (hasShot && body.includes("打开中"));
    const sample = shot
      ? `shot=${(shot.getAttribute("src") ?? "").slice(0, 32)}… alt=${shot.getAttribute("alt") ?? ""}`
      : liveBadge
        ? "LIVE 徽标"
        : hasLiveWord
          ? "直播文案"
          : null;
    return { live, sample };
  });
}

type RunTimeline = {
  phases: string[];
  steps: string[];
  errored: boolean;
  liveSeen: boolean;
  liveSamples: string[];
};

/** 运行期每 4s 采样一次：记阶段、记步骤、看直播、盯错误。 */
async function collectRunTimeline(timeoutMs: number): Promise<RunTimeline> {
  const phases = new Set<string>();
  const steps: string[] = [];
  let lastDetail: string | null = null;
  let errored = false;
  let liveSeen = false;
  const liveSamples: string[] = [];

  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const probe = await probeWork();
    if (!probe.busy) break;
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

    const live = await probeLiveStream();
    if (live.live) {
      liveSeen = true;
      if (live.sample && liveSamples.length < 5 && !liveSamples.includes(live.sample)) {
        liveSamples.push(live.sample);
        log(SCOPE, `见到直播流：${live.sample}`);
      }
    }

    await browser.pause(TIMELINE_INTERVAL_MS);
  }

  return { phases: [...phases], steps, errored, liveSeen, liveSamples };
}

// ---------------------------------------------------------------------------
// 步骤块（`ui-ai/src/blocks/step.tsx`）：折叠 / 命令行 / 完整输出
// ---------------------------------------------------------------------------

type StepBlockProbe = {
  /** summary 全文：`标签 · 说明` + 右侧状态。 */
  summary: string;
  open: boolean;
  /** 有正文才会有折叠箭头；没正文的块点了也不展开。 */
  hasBody: boolean;
  /** 命令行（`$ tool search …`），收起时不在 DOM 里。 */
  command: string | null;
  /** 原始输出的字符数，收起时读不到。 */
  outputLength: number;
};

/**
 * 读所有步骤块。
 *
 * 收起时正文被 `Collapse` 卸载，所以 `command` / `outputLength` 只有在展开态才有值 ——
 * 调用方要先展开再断言这两项。
 */
function probeStepBlocks(): Promise<StepBlockProbe[]> {
  return browser.execute(() => {
    const text = (node: Element | null | undefined): string =>
      (node?.textContent ?? "").replace(/\s+/g, " ").trim();
    return Array.from(document.querySelectorAll('[data-testid="step-block"]')).map((node) => {
      const command = node.querySelector('[data-testid="step-terminal-command"]');
      const output = node.querySelector('[data-testid="step-terminal-output"]');
      return {
        summary: text(node.querySelector("summary")),
        open: node.hasAttribute("open"),
        hasBody: node.children.length > 1,
        command: command ? text(command).replace(/^\$\s*/, "") : null,
        outputLength: output ? text(output).length : 0,
      };
    });
  });
}

/** 给第 index 个步骤块的 summary 打标记（先清旧标记，见 README「已知坑」4）。 */
function markStepSummary(index: number): Promise<boolean> {
  return browser.execute<boolean, [string, number]>(
    (attr, target) => {
      document.querySelectorAll(`[${attr}]`).forEach((node) => node.removeAttribute(attr));
      const summary = document
        .querySelectorAll('[data-testid="step-block"]')
        [target]?.querySelector("summary");
      if (!summary) return false;
      summary.setAttribute(attr, "1");
      return true;
    },
    STEP_SUMMARY_ATTR,
    index,
  );
}

/** 真实点击第 index 个步骤块的标题栏（展开 / 收起都走它）。 */
async function clickStepSummary(index: number): Promise<void> {
  if (!(await markStepSummary(index))) throw new Error(`找不到第 ${index} 个步骤块`);
  await (await $(`[${STEP_SUMMARY_ATTR}="1"]`)).click();
}

function isStepOpen(index: number): Promise<boolean> {
  return browser.execute<boolean, [number]>(
    (target) =>
      document
        .querySelectorAll('[data-testid="step-block"]')
        [target]?.hasAttribute("open") ?? false,
    index,
  );
}

/** 展开所有收起的步骤块，返回展开个数（全展开时返回 0）。 */
async function expandStepBlocks(): Promise<number> {
  const closed = await browser.execute<number[], []>(() =>
    Array.from(document.querySelectorAll('[data-testid="step-block"]'))
      .map((node, index) => (node.hasAttribute("open") ? -1 : index))
      .filter((index) => index >= 0),
  );
  for (const index of closed) {
    await clickStepSummary(index);
  }
  if (closed.length > 0) await browser.pause(300);
  return closed.length;
}

/** 面向用户的动作文案；出现其一即说明工具身份被还原了（不再全是「执行操作」）。 */
const BUSINESS_LABEL = /搜索商品|查看商品详情|连贯浏览|预览网页|扫码登录|比价找同款/;

/**
 * 裸入口命令行：`tool <子命令> …`。
 *
 * 不锚定行首 —— agent runtime 会把自己的 shell 包在外面（codex 实测是
 * `"…\powershell.exe" -Command 'tool search …'`），那是运行时的锅，不是我们的路径。
 * 要证的是「业务工具本身用裸 bin 调，不再拼解释器与脚本路径」。
 */
const BARE_ENTRY = /\btool(?:\.exe)?\s+(search|product|browse|preview|login|compare)\b/;

/** 旧入口痕迹：解释器路径 / 仓库脚本 / 包入口，一律不许出现在展示的命令行里。 */
const LEGACY_ENTRY = /run_tool\.py|tools[./\\]cli|dingda-skills[/\\]scripts/;

// ---------------------------------------------------------------------------
// 中文判定
// ---------------------------------------------------------------------------

/** 是否算「中文内容」：至少 4 个汉字。 */
function hasChinese(text: string): boolean {
  return (text.match(/[\u4e00-\u9fff]/g) ?? []).length >= 4;
}

/** 最长的连续 ASCII 英文串长度（URL / JSON / 命令会拉长它，故阈值给得宽松）。 */
function longestEnglishRun(text: string): number {
  const runs = text.match(/[A-Za-z][A-Za-z0-9 ,.'"()\-_/]{19,}/g) ?? [];
  return runs.reduce((max, run) => Math.max(max, run.length), 0);
}

/**
 * 展开所有「Thought for …」思考块，返回它们的正文。
 *
 * 思考块在流式期间不渲染正文（`thinking.tsx` 对 `streaming` 直接 return null），
 * 结束后折叠成一行摘要，**必须点开才读得到内容** —— 所以这里先打标记再点 summary。
 */
async function readThoughtTexts(): Promise<string[]> {
  await browser.execute<void, [string]>((attr) => {
    document.querySelectorAll(`[${attr}]`).forEach((node) => node.removeAttribute(attr));
    const details = Array.from(document.querySelectorAll("details"));
    details.forEach((node, index) => {
      const summary = (node.querySelector("summary")?.textContent ?? "").trim();
      if (/thought/i.test(summary)) node.setAttribute(attr, String(index));
    });
  }, THOUGHT_ATTR);

  const count = await browser.execute<number, [string]>(
    (attr) => document.querySelectorAll(`[${attr}]`).length,
    THOUGHT_ATTR,
  );
  if (count === 0) return [];

  for (let index = 0; index < count; index += 1) {
    const handle = await $(`[${THOUGHT_ATTR}="${index}"] > summary`);
    await handle.click().catch(() => undefined);
  }
  await browser.pause(500);

  return browser.execute<string[], [string]>((attr) => {
    return Array.from(document.querySelectorAll(`[${attr}]`)).map(
      (node) => (node.textContent ?? "").replace(/\s+/g, " ").trim(),
    );
  }, THOUGHT_ATTR);
}

// ---------------------------------------------------------------------------
// 页面操作（真实点击）
// ---------------------------------------------------------------------------

/** 首页是否已渲染。 */
function homeReady(): Promise<boolean> {
  return browser.execute<boolean, [string]>(
    (selector) => Boolean(document.querySelector(selector)),
    HERO,
  );
}

function clearMarker(attribute: string): Promise<void> {
  return browser.execute<void, [string]>((attr) => {
    document.querySelectorAll(`[${attr}]`).forEach((node) => node.removeAttribute(attr));
  }, attribute);
}

/** 归位到首页：URL（含 hash）会跨应用实例残留，进来可能还在上个 spec 的工作页。 */
async function ensureHome(): Promise<void> {
  const hash = await browser.execute(() => window.location.hash);
  if (hash && hash !== "#/") {
    log(SCOPE, `进入时路由为 "${hash}"，点侧栏「首页」归位`);
    const home = await findButtonByText("首页", "exact");
    if (!home) throw new Error(`侧栏找不到「首页」\n${await dumpContext()}`);
    await home.click();
  }
  if (!(await waitUntil(homeReady, 20_000))) {
    throw new Error(`首页未渲染\n${await dumpContext()}`);
  }
}

/** 首页 Agent 下拉状态（trigger 必须限定在 home-hero 内，否则会命中右上角用户菜单）。 */
function agentMenuState(): Promise<{ open: boolean; triggerText: string | null; entries: string[] }> {
  return browser.execute(() => {
    const text = (node: Element | null | undefined): string =>
      (node?.textContent ?? "").replace(/\s+/g, " ").trim();
    const trigger = document.querySelector(
      '[data-testid="home-hero"] [data-slot="dropdown-menu-trigger"]',
    );
    const content = document.querySelector('[data-slot="dropdown-menu-content"]');
    return {
      open: Boolean(content),
      triggerText: trigger ? text(trigger) : null,
      entries: content
        ? Array.from(
            content.querySelectorAll(
              '[data-slot="dropdown-menu-sub-trigger"], [data-slot="dropdown-menu-item"]',
            ),
          ).map((node) => text(node))
        : [],
    };
  });
}

/** 模型子菜单状态。 */
function subMenuState(): Promise<{ open: boolean; items: string[] }> {
  return browser.execute(() => {
    const text = (node: Element | null | undefined): string =>
      (node?.textContent ?? "").replace(/\s+/g, " ").trim();
    const content = document.querySelector('[data-slot="dropdown-menu-sub-content"]');
    return {
      open: Boolean(content),
      items: content
        ? Array.from(content.querySelectorAll('[data-slot="dropdown-menu-item"]'))
            .map((node) => text(node))
            .slice(0, 40)
        : [],
    };
  });
}

/** `DINGDA_E2E_MODEL_ID` 的候选文案：下拉渲染的是 label，而人习惯按 id 指定。 */
function modelCandidates(agent: AgentRuntimeItem): string[] {
  if (!MODEL_ID) return [];
  const label = (agent.models ?? []).find((model) => model.id === MODEL_ID)?.label ?? null;
  return label && label !== MODEL_ID ? [MODEL_ID, label] : [MODEL_ID];
}

function pickModel(agent: AgentRuntimeItem, items: string[]): string | null {
  if (MODEL_ID) {
    const candidates = modelCandidates(agent);
    for (const wanted of candidates) {
      const exact = items.find((item) => item === wanted);
      if (exact) return exact;
    }
    for (const wanted of candidates) {
      const partial = items.find((item) => item.includes(wanted));
      if (partial) return partial;
    }
    return null;
  }
  const models = agent.models ?? [];
  const preferred = models.find((model) => model.id === agent.preferred_model_id)?.label ?? null;
  return (preferred && items.includes(preferred) ? preferred : items[0]) ?? null;
}

/** 在首页把 Composer 切到目标 Agent（必须点到一个模型才会触发 onChange）。 */
async function selectComposerAgent(agent: AgentRuntimeItem): Promise<void> {
  const initial = await agentMenuState();
  const agentMatched = Boolean(initial.triggerText?.includes(agent.name));
  const modelMatched =
    !MODEL_ID || modelCandidates(agent).some((wanted) => initial.triggerText?.includes(wanted));
  if (agentMatched && modelMatched) {
    log(SCOPE, `Agent 已是「${agent.name}」（${initial.triggerText}），跳过选择`);
    return;
  }

  await clearMarker(AGENT_TRIGGER_ATTR);
  const marked = await browser.execute<boolean, [string, string]>(
    (heroSelector, attr) => {
      const trigger = document
        .querySelector(heroSelector)
        ?.querySelector<HTMLElement>('[data-slot="dropdown-menu-trigger"]');
      if (!trigger) return false;
      trigger.setAttribute(attr, "1");
      return true;
    },
    HERO,
    AGENT_TRIGGER_ATTR,
  );
  if (!marked) throw new Error(`找不到 Agent 下拉\n${await dumpContext()}`);

  if (!(await agentMenuState()).open) {
    await (await $(`[${AGENT_TRIGGER_ATTR}]`)).click();
  }
  if (!(await waitUntil(async () => (await agentMenuState()).open, 15_000, 300))) {
    throw new Error(`Agent 下拉未展开\n${await dumpContext()}`);
  }

  await clearMarker(AGENT_SUB_ATTR);
  const subMarked = await browser.execute<boolean, [string, string]>(
    (name, attr) => {
      const content = document.querySelector('[data-slot="dropdown-menu-content"]');
      if (!content) return false;
      const hit = Array.from(
        content.querySelectorAll<HTMLElement>(
          '[data-slot="dropdown-menu-sub-trigger"], [data-slot="dropdown-menu-item"]',
        ),
      ).find((node) => (node.textContent ?? "").includes(name));
      if (!hit) return false;
      hit.setAttribute(attr, "1");
      return true;
    },
    agent.name,
    AGENT_SUB_ATTR,
  );
  if (!subMarked) {
    throw new Error(
      `下拉里找不到「${agent.name}」\n可见项：${JSON.stringify((await agentMenuState()).entries)}`,
    );
  }

  const subTrigger = await $(`[${AGENT_SUB_ATTR}]`);
  await subTrigger.click();
  if (!(await waitUntil(async () => (await subMenuState()).open, 8_000, 200))) {
    await subTrigger.moveTo();
    if (!(await waitUntil(async () => (await subMenuState()).open, 8_000, 200))) {
      throw new Error(`「${agent.name}」模型子菜单未展开`);
    }
  }

  const sub = await subMenuState();
  const wanted = pickModel(agent, sub.items);
  if (!wanted) {
    throw new Error(
      MODEL_ID
        ? `找不到模型「${MODEL_ID}」\n可见项：${JSON.stringify(sub.items)}`
        : `「${agent.name}」模型子菜单为空`,
    );
  }

  const before = (await agentMenuState()).triggerText;
  await clearMarker(AGENT_MODEL_ATTR);
  const modelMarked = await browser.execute<boolean, [string, string]>(
    (label, attr) => {
      const content = document.querySelector('[data-slot="dropdown-menu-sub-content"]');
      if (!content) return false;
      const hit = Array.from(
        content.querySelectorAll<HTMLElement>('[data-slot="dropdown-menu-item"]'),
      ).find((node) => (node.textContent ?? "").trim() === label);
      if (!hit) return false;
      hit.setAttribute(attr, "1");
      return true;
    },
    wanted,
    AGENT_MODEL_ATTR,
  );
  if (!modelMarked) throw new Error(`子菜单找不到模型「${wanted}」`);
  await (await $(`[${AGENT_MODEL_ATTR}]`)).click();

  // 判「选中成功」看触发器文案变化，不看下拉是否收起。
  const changed = await waitUntil(async () => {
    const state = await agentMenuState();
    return state.triggerText !== before && Boolean(state.triggerText?.includes(agent.name));
  }, 15_000, 300);
  if (!changed) {
    throw new Error(
      `选择后触发器未变（${before} → ${(await agentMenuState()).triggerText}）`,
    );
  }
  log(SCOPE, `已选 Agent：${(await agentMenuState()).triggerText}`);
}

/** 把提示词敲进输入框（WebDriver 对中文 IME 兼容有差异，故带原生 setter 兜底）。 */
async function typePrompt(prompt: string): Promise<void> {
  const textarea = await $(`${HERO} [data-slot="textarea"]`);
  await textarea.setValue(prompt);

  const typed = await browser.execute<string, [string]>(
    (heroSelector) =>
      document.querySelector<HTMLTextAreaElement>(`${heroSelector} [data-slot="textarea"]`)
        ?.value ?? "",
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
      document.querySelector<HTMLTextAreaElement>(`${heroSelector} [data-slot="textarea"]`)
        ?.value ?? "",
    HERO,
  );
  if (finalValue.trim() !== prompt) {
    throw new Error(`输入框内容不对（期望 ${prompt.length} 字，实际 ${finalValue.length} 字）`);
  }
}

async function submitPrompt(): Promise<void> {
  await (await $('button[aria-label="发送"]')).click();
  log(SCOPE, "已点击发送");
}

async function waitForWorkRoute(timeoutMs = 30_000): Promise<string> {
  if (!(await waitUntil(async () => (await probeWork()).workId !== null, timeoutMs, 300))) {
    throw new Error(`未跳转到工作页\n${await dumpContext()}`);
  }
  const workId = (await probeWork()).workId ?? "";
  log(SCOPE, `已进入工作页：${workId}`);
  return workId;
}

/** 等运行真正开始（判据是 `Agent working`，不是停止按钮）。 */
async function waitForRunStart(
  timeoutMs = START_TIMEOUT_MS,
): Promise<{ started: boolean; error: string | null }> {
  let error: string | null = null;
  const started = await waitUntil(async () => {
    if ((await workingIndicator()).present) return true;
    const probe = await probeWork();
    if (probe.errorText) {
      error = probe.errorText;
      return true;
    }
    return false;
  }, timeoutMs, 300);
  return { started, error };
}

async function cancelRun(): Promise<void> {
  await (await $('button[aria-label="停止生成"]')).click();
  log(SCOPE, "已点击「停止生成」");
}

/** 等后端落库到最终态（前端 can_send 为真时才 flush 持久化）。 */
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

function dumpArtifact(name: string, payload: unknown): string | null {
  try {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const file = path.join(ARTIFACT_DIR, `${name}-${stamp}.json`);
    fs.writeFileSync(file, JSON.stringify(payload, null, 2), "utf8");
    return file;
  } catch (error) {
    console.warn(`[${SCOPE}] 落盘失败：${String(error)}`);
    return null;
  }
}

// ---------------------------------------------------------------------------
// 用例
// ---------------------------------------------------------------------------

describe(`Codex 找商品：出商品 + 出直播流 + 全程中文（agent=${AGENT_ID}）`, () => {
  let agent: AgentRuntimeItem | null = null;

  before(async () => {
    if (!(await waitForPort(E2E_PORT, 90_000))) {
      throw new Error(`等待 Python Server 监听 ${E2E_PORT} 超时`);
    }
    await disableAutoFocus();
    await waitForAppShell();

    const agents = await fetchAgentRuntimes(E2E_PORT);
    const target = agents.find((item) => item.id === AGENT_ID) ?? null;
    if (target?.available) {
      agent = target;
      log(
        SCOPE,
        `目标 Agent=${target.name}（${target.id}）模型 ${target.models?.length ?? 0} 个，` +
          `首选=${target.preferred_model_id ?? "（未设置）"}`,
      );
    } else {
      log(
        SCOPE,
        `未找到可用的「${AGENT_ID}」（目录 ${agents.length} 个：${agents
          .map((item) => `${item.id}${item.available ? "" : "(不可用)"}`)
          .join("、")}），本轮跳过。`,
      );
    }
  });

  it("发起找商品 → 跑完 → 有商品、有直播流、思考与回复都是中文", async () => {
    if (!agent) {
      log(SCOPE, `跳过：环境里没有可用的 ${AGENT_ID}。`);
      return;
    }

    await ensureHome();
    await selectComposerAgent(agent);
    await typePrompt(PROMPT);
    await submitPrompt();

    const workId = await waitForWorkRoute();

    const start = await waitForRunStart();
    if (start.error) {
      throw new Error(`发送后运行失败：${start.error}\n${await dumpContext()}`);
    }
    if (!start.started) {
      throw new Error(
        `发送后运行未启动（${START_TIMEOUT_MS / 1000}s 内没出现「Agent working」）\n` +
          `${await dumpContext()}`,
      );
    }

    if (DRY_RUN) {
      log(SCOPE, "干跑：已启动，点停止");
      await cancelRun();
      const stopped = await waitUntil(async () => !(await probeWork()).busy, 60_000, 500);
      expect(stopped).toBe(true);
      return;
    }

    log(SCOPE, `运行已启动，分步采样中（上限 ${RUN_TIMEOUT_MS / 1000}s）…`);
    const timeline = await collectRunTimeline(RUN_TIMEOUT_MS);

    if (timeline.errored) {
      const probe = await probeWork();
      await cancelRun().catch(() => undefined);
      throw new Error(
        `运行中途报错（已取消）：${probe.errorText ?? "（无）"}\n` +
          `阶段：${JSON.stringify(timeline.phases)}\n步骤：${JSON.stringify(timeline.steps)}`,
      );
    }

    const probe = await probeWork();
    if (probe.busy) {
      throw new Error(
        `等待运行结束超时（${RUN_TIMEOUT_MS / 1000}s）\n` +
          `阶段：${JSON.stringify(timeline.phases)}\n步骤：${JSON.stringify(timeline.steps)}`,
      );
    }
    log(
      SCOPE,
      `运行结束：面板=${probe.resultPanel} 计数=${probe.totalText ?? "（无）"} ` +
        `标题 ${probe.titles.length} 条 错误=${probe.errorText ?? "（无）"}`,
    );

    // —— 结构判定：真的调过工具，且至少一步是搜索类 ——
    expect(timeline.steps.length).toBeGreaterThan(0);
    expect(timeline.phases.length).toBeGreaterThan(0);
    const skillLike = timeline.steps.some((step) =>
      /搜索|search|闲鱼|小红书|1688|爬取|商品/i.test(step),
    );
    expect(skillLike).toBe(true);
    log(SCOPE, `工具步骤：${timeline.steps.join(" → ")}`);

    // —— 直播流三重取证 ——
    let liveSeen = timeline.liveSeen;
    const liveSamples = [...timeline.liveSamples];
    if (!liveSeen) {
      const after = await probeLiveStream();
      if (after.live) {
        liveSeen = true;
        if (after.sample) liveSamples.push(after.sample);
        log(SCOPE, `跑完后补见到直播痕迹：${after.sample}`);
      }
    }
    const snapshot = await waitForPersistedWork(workId);
    const reply = lastAssistantText(snapshot);
    // 落盘早于断言：断言失败时不必再复跑一轮（一轮十几分钟）就能看到落库与页面实况。
    const thoughts = await readThoughtTexts();
    const blocksCollapsed = await probeStepBlocks();
    const expandedByTest = await expandStepBlocks();
    const blocksExpanded = await probeStepBlocks();
    const artifact = dumpArtifact(`codex-product-${workId}`, {
      workId,
      agent: agent.id,
      prompt: PROMPT,
      timeline,
      ui: probe,
      blocksCollapsed,
      blocksExpanded,
      expandedByTest,
      api: snapshot,
      reply,
      thoughts,
    });
    if (artifact) log(SCOPE, `结果已落盘：${artifact}`);

    const historyShots = (snapshot?.browser_history ?? []).filter((frame) =>
      Boolean(frame.screenshot_url),
    );
    if (historyShots.length > 0) {
      liveSeen = true;
      liveSamples.push(`browser_history ${historyShots.length} 帧`);
    }
    expect(liveSeen).toBe(true);
    log(SCOPE, `直播流证据：${JSON.stringify(liveSamples)}`);

    // —— 步骤块：工具身份是否还原 ——
    // 放在商品之前：它不依赖商品条数，而商品受模型「是否等命令返回」影响会偶发为 0，
    // 那条环境性失败不该把「工具身份 / 折叠 / 命令行」的结论一起遮掉。
    expect(blocksExpanded.length).toBeGreaterThan(0);
    const labeled = blocksExpanded.filter((block) => BUSINESS_LABEL.test(block.summary));
    expect(labeled.length).toBeGreaterThan(0);
    log(
      SCOPE,
      `步骤块 ${blocksExpanded.length} 个，业务文案 ${labeled.length} 个：` +
        JSON.stringify(blocksExpanded.map((block) => block.summary)),
    );

    // —— 折叠往返：真实点标题栏，开合状态必须真的翻转 ——
    const toggleIndex = blocksExpanded.findIndex((block) => block.hasBody);
    expect(toggleIndex).toBeGreaterThanOrEqual(0);
    const wasOpen = await isStepOpen(toggleIndex);
    await clickStepSummary(toggleIndex);
    const afterClick = await isStepOpen(toggleIndex);
    expect(afterClick).toBe(!wasOpen);
    await clickStepSummary(toggleIndex);
    expect(await isStepOpen(toggleIndex)).toBe(wasOpen);
    log(SCOPE, `折叠往返正常（第 ${toggleIndex} 块 ${wasOpen} → ${afterClick} → ${wasOpen}）`);

    // —— 命令行块：裸 `tool <子命令>`，旧解释器/脚本路径不许再出现 ——
    const commands = blocksExpanded
      .map((block) => block.command)
      .filter((command): command is string => command !== null);
    expect(commands.length).toBeGreaterThan(0);
    expect(commands.filter((command) => BARE_ENTRY.test(command)).length).toBeGreaterThan(0);
    expect(commands.filter((command) => LEGACY_ENTRY.test(command))).toHaveLength(0);
    log(SCOPE, `命令行 ${commands.length} 条：${JSON.stringify(commands.slice(0, 4))}`);

    // —— 完整输出：折叠区里能读到成规模的原始返回 ——
    const longestOutput = Math.max(0, ...blocksExpanded.map((block) => block.outputLength));
    expect(longestOutput).toBeGreaterThan(200);
    log(SCOPE, `最长原始输出 ${longestOutput} 字`);

    // —— 商品：页面 + 落库两侧都要有 ——
    expect(probe.errorText ?? null).toBeNull();
    expect(probe.resultPanel).toBe(true);
    expect(probe.totalText).not.toBeNull();
    const uiTotal = Number((probe.totalText ?? "").match(/(\d+)/)?.[1] ?? 0);
    expect(uiTotal).toBeGreaterThanOrEqual(MIN_PRODUCTS);
    expect(probe.titles.length).toBeGreaterThan(0);

    expect(snapshot).not.toBeNull();
    const apiItems = snapshot?.products?.items ?? [];
    expect(apiItems.length).toBeGreaterThanOrEqual(MIN_PRODUCTS);
    expect(snapshot?.products?.total ?? 0).toBeGreaterThanOrEqual(MIN_PRODUCTS);
    expect(snapshot?.composer_agent_id ?? null).toBe(agent.id);
    log(
      SCOPE,
      `页面 ${uiTotal} 条 / 落库 ${apiItems.length} 条；样例：` +
        `${apiItems.slice(0, 3).map((item) => `${item.title}（${item.price || "无价"}）`).join(" | ")}`,
    );
    const matched = probe.titles.filter((title) =>
      apiItems.some((item) => item.title === title),
    );
    expect(matched.length).toBeGreaterThan(0);

    expect(hasChinese(reply)).toBe(true);
    const replyRun = longestEnglishRun(reply);
    if (replyRun > 120) {
      throw new Error(
        `助手回复出现 ${replyRun} 字连续英文，疑似没按中文输出：${reply.slice(0, 200)}`,
      );
    }
    log(SCOPE, `助手回复 ${reply.length} 字，最长英文串 ${replyRun}；摘要：${reply.slice(0, 80)}`);

    // —— 中文：思考块（有就必须中文）——
    if (thoughts.length === 0) {
      log(SCOPE, "页面上没有思考块（模型未输出 thinking），跳过思考语言断言");
    } else {
      const badThought = thoughts.find((text) => text.length > 20 && !hasChinese(text));
      if (badThought) {
        throw new Error(
          `思考块不是中文：${badThought.slice(0, 200)}\n完整快照：${artifact ?? "（未落盘）"}`,
        );
      }
      log(SCOPE, `思考块 ${thoughts.length} 个，均为中文（最长 ${Math.max(...thoughts.map((t) => t.length))} 字）`);
    }
  });
});
