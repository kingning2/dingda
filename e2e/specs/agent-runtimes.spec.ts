/**
 * Agent 检测与模型选择 E2E。
 *
 * 覆盖两条用户可见链路：
 *   1. **检测**：侧栏进 Agent 页 → 点「扫描 Agent」→ 页面「已检测到（N）」与实际
 *      落库目录一致；
 *   2. **模型选择**：在某张 Agent 卡片的「可用模型」下拉里换一个模型 → 页面回显与
 *      `GET /v1/agent/preferences` 的 `default_models` 一致。
 *
 * ## 驱动原则
 * 全程点页面上的按钮 / 下拉，不直接打 `PUT /v1/agent/default-model` 推进流程。
 * 测试进程只做旁证：扫描前后读目录、切模型前后读偏好。
 *
 * ## 关于副作用（重要）
 * - 「扫描 Agent」会把探测结果**写回** `app_settings.agent_runtimes_catalog`。这是该
 *   按钮的本职行为，且写的是可重建的缓存，不是用户偏好。
 * - 模型选择会写 `default_models`，**那是用户的真实偏好**。所以本用例做**往返验证**：
 *   先记下原值 → 换成另一个 → 校验 → **用 UI 改回原值**再校验。
 *   若还原在 UI 上失败，才用 `putDefaultModel` 兜底，并在日志里明确标出走了兜底。
 * - 本用例**不改**默认 Agent（那需要用户明确要求）。
 *
 * ## 选择器
 * 一律用源码里写死的 `data-slot`：
 *   - 面板：「扫描 Agent」按钮按可见文本筛；计数读 `h2` 的「已检测到（N）」；
 *   - 卡片：`[data-slot="card"]`（ui-primitives/card.tsx）；
 *   - 下拉：`[data-slot="select-trigger"|"select-value"|"select-content"|"select-item"]`
 *     （ui-primitives/select.tsx）。
 * 多张卡片各有一个下拉，所以先用 `browser.execute` 给目标元素打一个临时属性
 * `data-e2e-target`，再用 WDIO 去点它 —— 精确定位与真实点击兼得。
 *
 * 性能陷阱（每命令 5 秒的自动聚焦）与超时约定见 `helpers/ui.ts` 与 `wdio.conf.ts`。
 */
import { $, browser, expect } from "@wdio/globals";

import {
  fetchAgentPreferences,
  fetchAgentRuntimes,
  pickAgentForModelRoundTrip,
  putDefaultModel,
  type AgentRuntimeItem,
} from "../helpers/agent";
import { waitForPort } from "../helpers/desktop";
import {
  clickNavItem,
  disableAutoFocus,
  dumpContext,
  findButtonByText,
  log,
  waitForAppShell,
  waitUntil,
} from "../helpers/ui";

const SCOPE = "agent";

/** wdio.conf.ts 顶层已把它写入 DINGDA_PORT（同一个值传给被测应用）。 */
const E2E_PORT = Number(process.env.DINGDA_PORT ?? 8799);

/** 手动扫描要跑 PATH 探测 + 逐个 Agent 深探测，给足余量。 */
const SCAN_TIMEOUT_MS = 180_000;
/** 下拉展开 / 收起的等待。 */
const SELECT_TIMEOUT_MS = 20_000;

// ---------------------------------------------------------------------------
// 页面探测（一律走 execute，避开 focusCommands）
// ---------------------------------------------------------------------------

type PanelState = {
  mounted: boolean;
  scanLabel: string | null;
  scanDisabled: boolean | null;
  detectedCount: number;
  missingCount: number;
};

/** 读 Agent 面板状态。 */
function panelState(): Promise<PanelState> {
  return browser.execute(() => {
    const headings = Array.from(document.querySelectorAll("h2")).map((node) =>
      (node.textContent ?? "").trim(),
    );
    const countOf = (prefix: string): number => {
      const hit = headings.find((text) => text.startsWith(prefix));
      const matched = hit?.match(/（(\d+)）/);
      return matched ? Number(matched[1]) : 0;
    };
    const scanButton = Array.from(document.querySelectorAll("button")).find((node) =>
      (node.textContent ?? "").includes("扫描"),
    );
    return {
      mounted: Boolean(scanButton),
      scanLabel: scanButton
        ? (scanButton.textContent ?? "").replace(/\s+/g, " ").trim()
        : null,
      scanDisabled: scanButton ? (scanButton as HTMLButtonElement).disabled : null,
      detectedCount: countOf("已检测到"),
      missingCount: countOf("未安装"),
    };
  });
}

/**
 * 临时标记用的属性名。
 *
 * 为什么不用同一个属性名 + 统一清空：`markModelItem` 若清掉全部标记，会把触发器的标记
 * 也一并清掉，导致下一次 `openModelSelect` 找不到触发器。故两者各自独立清理。
 *
 * 为什么每次都要先清：下拉的内容容器**可能不随收起而卸载**，上一轮标记过的旧元素仍在
 * DOM 里；不清的话 `$()` 按文档顺序会命中旧元素 —— 点了等于没点，而且**静默通过**
 * （第一次跑就踩了这个）。
 */
const TRIGGER_ATTR = "data-e2e-trigger";
const ITEM_ATTR = "data-e2e-item";

/** 清掉指定属性的所有标记，保证选择器只命中一个元素。 */
function clearMarker(attribute: string): Promise<void> {
  return browser.execute((attr: string) => {
    document.querySelectorAll(`[${attr}]`).forEach((node) => node.removeAttribute(attr));
  }, attribute);
}

/** 给指定 Agent 卡片里的下拉触发器打标记，返回是否找到。 */
async function markModelTrigger(agentName: string): Promise<boolean> {
  await clearMarker(TRIGGER_ATTR);
  return browser.execute(
    (name: string, attr: string) => {
      const cards = Array.from(document.querySelectorAll('[data-slot="card"]'));
      for (const card of cards) {
        const named = Array.from(card.querySelectorAll("p")).some(
          (node) => (node.textContent ?? "").trim() === name,
        );
        if (!named) continue;
        const trigger = card.querySelector<HTMLElement>('[data-slot="select-trigger"]');
        if (!trigger) return false;
        trigger.setAttribute(attr, "1");
        return true;
      }
      return false;
    },
    agentName,
    TRIGGER_ATTR,
  );
}

type SelectState = {
  triggerPresent: boolean;
  triggerDisabled: boolean | null;
  contentOpen: boolean;
  itemCount: number;
  itemLabels: string[];
  valueText: string | null;
};

/** 读已标记下拉的状态与当前选项文本。 */
function modelSelectState(): Promise<SelectState> {
  return browser.execute((attr: string) => {
    const trigger = document.querySelector(`[${attr}]`);
    const content = document.querySelector('[data-slot="select-content"]');
    const items = content
      ? Array.from(content.querySelectorAll('[data-slot="select-item"]'))
      : [];
    const value = trigger?.querySelector('[data-slot="select-value"]');
    return {
      triggerPresent: Boolean(trigger),
      triggerDisabled: trigger ? (trigger as HTMLButtonElement).disabled : null,
      contentOpen: Boolean(content),
      itemCount: items.length,
      itemLabels: items.map((node) => (node.textContent ?? "").trim()).slice(0, 12),
      valueText: value ? (value.textContent ?? "").trim() : null,
    };
  }, TRIGGER_ATTR);
}

/** 给下拉里文本等于 `label` 的选项打标记。 */
async function markModelItem(label: string): Promise<boolean> {
  await clearMarker(ITEM_ATTR);
  return browser.execute(
    (target: string, attr: string) => {
      const content = document.querySelector('[data-slot="select-content"]');
      if (!content) return false;
      const items = Array.from(content.querySelectorAll('[data-slot="select-item"]'));
      const hit = items.find((node) => (node.textContent ?? "").trim() === target);
      if (!hit) return false;
      hit.setAttribute(attr, "1");
      return true;
    },
    label,
    ITEM_ATTR,
  );
}

// ---------------------------------------------------------------------------
// 页面操作（真实点击）
// ---------------------------------------------------------------------------

/** 进 Agent 页：点侧栏主导航的「Agent」。 */
async function openAgentsPage(): Promise<void> {
  log(SCOPE, "点击侧栏导航「Agent」");
  await clickNavItem("Agent");

  if (!(await waitUntil(async () => (await panelState()).mounted, 30_000))) {
    throw new Error(`Agent 面板未渲染\n现场快照：${await dumpContext()}`);
  }
  log(SCOPE, "Agent 面板已渲染");
}

/** 点「扫描 Agent」并等它跑完（按钮文案回到「扫描 Agent」且不再 disabled）。 */
async function runRescan(): Promise<void> {
  // 用 `$$("button")` + 文本筛，不用 XPath —— 与 helpers/ui 的定位策略保持一致。
  const button = await findButtonByText("扫描 Agent");
  if (!button) throw new Error(`找不到「扫描 Agent」按钮\n现场快照：${await dumpContext()}`);

  log(SCOPE, `点击「${(await button.getText()).trim()}」`);
  await button.click();

  // 先等「扫描中…」出现，否则下面的「回到扫描 Agent」会在点击后的瞬间就判真
  // （React 还没把 scanning 刷进 store），导致后续断言与扫描过程竞态。
  // 扫描很快时这一步可能等不到，属正常，故不判失败。
  const sawScanning = await waitUntil(async () => {
    const state = await panelState();
    return state.scanLabel === "扫描中…" || state.scanDisabled === true;
  }, 10_000, 200);
  log(SCOPE, sawScanning ? "已进入扫描中状态" : "（未捕捉到「扫描中…」，可能扫描极快）");

  const settled = await waitUntil(async () => {
    const state = await panelState();
    return state.scanLabel === "扫描 Agent" && state.scanDisabled === false;
  }, SCAN_TIMEOUT_MS, 1_000);

  if (!settled) {
    throw new Error(
      `等待扫描结束超时（${SCAN_TIMEOUT_MS / 1000}s）\n` +
        `面板状态：${JSON.stringify(await panelState())}`,
    );
  }
  log(SCOPE, "扫描已完成");
}

/** 打开已标记的模型下拉；已展开则直接用（否则点触发器会把它**收起**）。 */
async function openModelSelect(): Promise<SelectState> {
  if (!(await modelSelectState()).contentOpen) {
    const trigger = await $(`[${TRIGGER_ATTR}]`);
    await trigger.click();
  }

  const opened = await waitUntil(
    async () => (await modelSelectState()).contentOpen,
    SELECT_TIMEOUT_MS,
  );
  if (!opened) {
    throw new Error(`模型下拉未展开\n现场快照：${await dumpContext()}`);
  }
  return modelSelectState();
}

/**
 * 在下拉里选中文本为 `label` 的模型。
 *
 * 判定「选中成功」用的是**触发器文案发生变化**，而不是「下拉收起」—— 实测下拉点完
 * 并不必然收起，只等收起会静默放过「点了等于没点」的情况（第一次跑就踩了这个）。
 */
async function pickModel(label: string): Promise<void> {
  const before = (await modelSelectState()).valueText;

  if (!(await markModelItem(label))) {
    throw new Error(
      `下拉里找不到模型「${label}」\n` +
        `可见选项：${JSON.stringify((await modelSelectState()).itemLabels)}`,
    );
  }
  const item = await $(`[${ITEM_ATTR}]`);
  await item.click();

  const changed = await waitUntil(
    async () => (await modelSelectState()).valueText !== before,
    SELECT_TIMEOUT_MS,
    500,
  );
  if (!changed) {
    throw new Error(
      `点击模型「${label}」后触发器文案未变化（仍为 ${before}）\n` +
        `现场快照：${await dumpContext()}`,
    );
  }
}

/**
 * 等偏好落库到指定值。
 *
 * **必须轮询**，不能单次读：`pickModel` 只保证「触发器文案变了」，而
 * `PUT /v1/agent/default-model` 是点击后异步发出的，可能还在飞 —— 单次读会读到旧值
 * 而误判失败（第一次全量跑就踩了这个，见 README 已知坑）。
 */
async function waitForSavedModel(
  agentId: string,
  modelId: string,
  timeoutMs = 10_000,
): Promise<boolean> {
  return waitUntil(async () => {
    const preferences = await fetchAgentPreferences(E2E_PORT);
    return preferences.default_models[agentId] === modelId;
  }, timeoutMs, 500);
}

/**
 * 还原某 Agent 的默认模型。
 *
 * 先走 UI（这是被测路径），失败才用接口兜底 —— 兜底会明确告警，不静默。
 * 返回是否已确认还原。
 */
async function restorePreference(
  agent: AgentRuntimeItem,
  originalId: string,
  originalLabel: string | null,
): Promise<boolean> {
  try {
    if (!originalLabel) throw new Error("原偏好不在当前模型列表里，UI 无法选中");
    await openModelSelect();
    await pickModel(originalLabel);
  } catch (error) {
    console.warn(
      `[${SCOPE}] UI 还原失败，改用接口兜底（PUT /v1/agent/default-model）：${String(error)}`,
    );
    try {
      await putDefaultModel(E2E_PORT, agent.id, originalId);
    } catch (fallbackError) {
      console.error(`[${SCOPE}] 接口兜底也失败：${String(fallbackError)}`);
      return false;
    }
  }

  return waitForSavedModel(agent.id, originalId);
}

// ---------------------------------------------------------------------------
// 用例
// ---------------------------------------------------------------------------

describe("Agent 检测与模型选择", () => {
  /** 扫描前落库的目录，用于对比「扫描后仍一致」。 */
  let catalogBefore: AgentRuntimeItem[] = [];

  before(async () => {
    // 壳会自己拉起 Python Server，但 WebDriver session 建好时它可能还没监听上。
    if (!(await waitForPort(E2E_PORT, 90_000))) {
      throw new Error(`等待 Python Server 监听 ${E2E_PORT} 超时`);
    }
    // 必须早于任何元素操作：去掉 tauri-service 每个命令 5 秒的自动聚焦开销。
    await disableAutoFocus();
    await waitForAppShell();

    catalogBefore = await fetchAgentRuntimes(E2E_PORT);
    log(
      SCOPE,
      `扫描前落库目录：${catalogBefore.length} 个（可用 ${catalogBefore.filter((a) => a.available).length}）`,
    );
  });

  it("侧栏进入 Agent 页，页面展示的检测结果与落库目录一致", async () => {
    await openAgentsPage();

    const state = await panelState();
    log(
      SCOPE,
      `面板：「已检测到（${state.detectedCount}）」「未安装（${state.missingCount}）」`,
    );

    const availableFromApi = catalogBefore.filter((agent) => agent.available).length;
    expect(availableFromApi).toBeGreaterThan(0);
    expect(state.detectedCount).toBe(availableFromApi);
  });

  it("点「扫描 Agent」完成一次检测，结果与落库目录一致", async () => {
    await runRescan();

    const after = await fetchAgentRuntimes(E2E_PORT);
    const state = await panelState();
    log(
      SCOPE,
      `扫描后：落库 ${after.length} 个（可用 ${after.filter((a) => a.available).length}），` +
        `页面「已检测到（${state.detectedCount}）」`,
    );

    expect(after.length).toBeGreaterThan(0);
    expect(state.detectedCount).toBe(after.filter((agent) => agent.available).length);
  });

  it("在某 Agent 卡片切换模型并落库，随后用 UI 还原原值", async () => {
    const agents = await fetchAgentRuntimes(E2E_PORT);
    const preferences = await fetchAgentPreferences(E2E_PORT);
    const target = pickAgentForModelRoundTrip(agents, preferences.default_models);

    if (!target) {
      log(SCOPE, "没有「可用且模型数 ≥2」的 Agent，跳过模型切换验证。");
      return;
    }

    const models = target.models ?? [];
    const originalId = preferences.default_models[target.id] ?? null;
    const originalLabel = models.find((model) => model.id === originalId)?.label ?? null;
    log(
      SCOPE,
      `目标 Agent=${target.name}（${target.id}）模型 ${models.length} 个，` +
        `原偏好=${originalId ?? "（未设置）"}`,
    );

    /** 已经改成了什么；非 null 表示需要在 finally 里还原。 */
    let mutated: string | null = null;

    try {
      // 等卡片上的下拉可用（刚扫完时可能还在 probing）。
      await waitUntil(async () => {
        await markModelTrigger(target.name);
        return (await modelSelectState()).triggerDisabled === false;
      }, 60_000, 1_000);

      const before = await openModelSelect();
      log(SCOPE, `下拉已展开，可见 ${before.itemCount} 项，当前值=${before.valueText}`);
      expect(before.itemCount).toBeGreaterThanOrEqual(2);

      // 选一个「与当前不同」的可见选项，保证状态真的发生变化。
      const targetLabel = before.itemLabels.find((label) => label !== before.valueText);
      if (!targetLabel) throw new Error("下拉里找不到与当前值不同的选项");
      const targetModel = models.find((model) => model.label === targetLabel);
      if (!targetModel) throw new Error(`选项「${targetLabel}」不在接口返回的模型列表里`);

      log(SCOPE, `选择「${targetLabel}」`);
      await pickModel(targetLabel);
      mutated = targetModel.id;

      const afterPick = await modelSelectState();
      // 触发器文案变了才算真的切了。
      // 期望显示的是 **label**（agent-runtime-card 给 `Select` 传了 `items` 做
      // value→label 映射；不传的话 base-ui 会回落成原始 value=模型 id）。
      // 断言放宽到「id 或 label」只是为了不因上游/样式微调误报，日志会打出实际形态。
      expect(afterPick.valueText).not.toBe(before.valueText);
      expect([targetModel.id, targetModel.label]).toContain(afterPick.valueText);
      log(SCOPE, `触发器现在显示：${afterPick.valueText}（模型 id=${targetModel.id}）`);

      // 独立取证：偏好真的落库了。轮询 —— 点击后 PUT 可能还在飞。
      const saved = await waitForSavedModel(target.id, targetModel.id);
      expect(saved).toBe(true);
      log(SCOPE, `已落库：${target.id} → ${targetModel.id}`);
    } finally {
      // 还原必须放在 finally：否则中途断言失败会把用户的真实偏好留在改动后的值上
      // （第一次跑就踩了这个，见 README「已知坑」）。
      if (mutated !== null && originalId !== null && originalId !== mutated) {
        const restored = await restorePreference(target, originalId, originalLabel);
        if (!restored) {
          throw new Error(
            `未能还原 ${target.id} 的默认模型：当前可能仍是 ${mutated}，原值是 ${originalId}，请手动改回`,
          );
        }
        log(SCOPE, `已还原：${target.id} → ${originalId}`);
      } else if (originalId === null) {
        log(SCOPE, "原本没有偏好（会回落到列表首项），无需还原。");
      }
    }
  });
});
