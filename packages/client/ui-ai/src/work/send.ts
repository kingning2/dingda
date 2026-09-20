/**
 * 发起 / 接回一次 Agent 运行，并把 SSE 事件折进 detail。
 *
 * 职责：
 *   从「用户按下发送」或「接回服务端还在跑的那一轮」到「运行结束」的全过程：
 *   乐观插入消息（或清空已有助手消息）→ 起 SSE → 每个事件更新一份新的
 *   AgentWorkDetailView 交给调用方 → 结束/失败时收尾。
 *
 * 设计说明：
 *   - run 的生命周期归服务端（`agent.runs`）：客户端断开只是退订。所以这里有两
 *     条起手路径 —— `send`（新开一轮）与 `attach`（接回在跑的那轮），两者共用同一个
 *     `RunFold`。离开页面走 `detach`：不看，但不叫停。
 *   - 本模块只做编排与状态推进；「工具输出 → 商品/比价视图」的解析在 agent-output.ts。
 *   - 前端**不猜**后端语义：`hasProducts` 由这里解析出结果后显式告知 reducer，
 *     因为「商品结果」不是后端的事件类型。
 *   - 冷启动时把叮答侧历史交给服务端压缩注入，前端只负责裁剪长度。
 *   - 本轮运行归哪个 work 要显式告诉服务端（`workId`）：断线后重进页面靠它找回在跑的
 *     那条 run，接回逻辑在 `chat/use-work-detail.ts`。
 */

import type { AgentEvent } from "@v2/contracts/agent-event";
import type { ComposerSubmitPayload } from "@v2/contracts/composer";
import type {
  AgentWorkAppraisalView,
  AgentWorkComparisonView,
  AgentWorkDetailView,
  AgentWorkSelectionView,
  AgentWorkMessageView,
} from "@v2/contracts/ai-work";
import type { CrawlProductItem } from "@v2/contracts/crawler";
import {
  applyRunStateToDetail,
  createAgentRunMessageState,
  createOptimisticSendDetail,
  reduceAgentEvent,
} from "@v2/ui-agent/run/reducer";
import type { AgentRunPhase } from "@v2/ui-agent/run/phase";
import {
  AgentStreamError,
  resumeAgentRun,
  startAgentRunWithEvents,
  type AgentRunHandle,
} from "@v2/ui-agent/run/stream";
import { extractAppraisal, extractComparison, extractProducts, extractSelection, mergeComparison, mergeProducts } from "./agent-output";

/** 一次运行的句柄：拿 runId、等结束、停止跟踪/叫停。 */
export interface SendHandle {
  runId: string;
  promise: Promise<AgentWorkDetailView>;
  /** 不看这一轮了，但让它在服务端继续跑。 */
  detach: () => void;
  cancel: () => Promise<void>;
}

/** 运行更新回调：同时返回对话快照和当前前端阶段。 */
export type SendUpdate = (next: AgentWorkDetailView, phase: AgentRunPhase) => void;

/** 注入历史的上限：条数与单条字符数。太长的历史对模型没用，只是浪费上下文。 */
const CONTEXT_MAX_MESSAGES = 30;
const CONTEXT_MAX_CHARS = 2000;
/** UI 更新的最小间隔：状态折叠和渲染合并，避免每个 SSE token 都整页重画。 */
const UI_COMMIT_MS = 60;

/** 掉线续传的次数与退避。覆盖短时抖动即可：长时间断网用户重进页面会冷接回。 */
const RECONNECT_BACKOFF_MS = [500, 1000, 2000, 4000, 8000];

/** 换 Agent 冷启动：从 work 消息抽出可注入的先前对话（不含本轮正在发的那句）。 */
function buildContextMessages(
  messages: AgentWorkMessageView[],
): Array<{ role: string; content: string }> {
  return messages
    .filter((item) => item.role === "user" || item.role === "assistant")
    .map((item) => ({
      role: item.role,
      content: item.content.trim().slice(0, CONTEXT_MAX_CHARS),
    }))
    .filter((item) => item.content)
    .slice(-CONTEXT_MAX_MESSAGES);
}

/**
 * 一轮运行的折叠态：状态机 + 落盘快照 + 已折叠到的服务端 seq。
 *
 * 初次发送与接回共用它 —— 两者的差别只在「第一次事件从哪来」，折叠本身一模一样。
 */
interface RunFold {
  /** 喂一个事件：先解析工具结果，再折叠、落盘、回调。 */
  fold: (event: AgentEvent) => void;
  /** 收尾：流结束但没收到 runCompleted 时补一次。 */
  settle: () => void;
  /** 失败收尾：进 failed 并放开继续发送。 */
  fail: (message: string) => void;
  /** 记服务端 seq：掉线后从这里续传，已折叠过的事件不重来。 */
  noteSeq: (seq: number) => void;
  /** 不再跟随：后续事件只进状态机，不再回调（离开页面时用）。 */
  stop: () => void;
  stopped: () => boolean;
  lastSeq: () => number;
  completed: () => boolean;
  snapshot: () => AgentWorkDetailView;
}

function createRunFold(
  detail: AgentWorkDetailView,
  assistantMessageId: string,
  onUpdate: SendUpdate,
  options?: { replaceComparisonFirst?: boolean },
): RunFold {
  let state = createAgentRunMessageState();
  let snapshot = detail;
  let lastSeq = 0;
  let stopped = false;
  // 接回时第一段重放的比价替换掉旧的而不是并上去：`mergeComparison` 按轮次累加，
  // 叠在上一轮已经算过的计数上会把候选数与轮次翻倍。
  let replaceComparison = options?.replaceComparisonFirst ?? false;

  const publish = () => {
    snapshot = applyRunStateToDetail(snapshot, assistantMessageId, state);
    if (!stopped) onUpdate(snapshot, state.phase);
  };
  let publishTimer: number | null = null;

  const cancelPublish = () => {
    if (publishTimer == null) return;
    window.clearTimeout(publishTimer);
    publishTimer = null;
  };

  const schedulePublish = () => {
    if (stopped || publishTimer != null) return;
    publishTimer = window.setTimeout(() => {
      publishTimer = null;
      publish();
    }, UI_COMMIT_MS);
  };

  return {
    lastSeq: () => lastSeq,
    completed: () => state.completed,
    stopped: () => stopped,
    snapshot: () => snapshot,
    stop: () => {
      stopped = true;
      cancelPublish();
    },
    noteSeq: (seq) => {
      lastSeq = seq;
    },
    fold: (event) => {
      if (stopped) return;
      // 工具结果先解析一遍：既决定阶段（products / executing），也拿到要并进 detail 的数据。
      let nextProducts: CrawlProductItem[] = [];
      let nextProductsStepId: string | null = null;
      let nextComparison: AgentWorkComparisonView | null = null;
      let nextSelection: AgentWorkSelectionView | null = null;
      let nextAppraisal: AgentWorkAppraisalView | null = null;
      if (event.type === "toolResult") {
        // 顺序有意义：选品与鉴定载荷都不带 platform，本来就不会被 extractProducts 认领，
        // 但先判它们更稳 —— 将来谁给载荷加回平台字段，这里也不会被商品面板吞掉。
        nextSelection = extractSelection(event.output);
        if (!nextSelection) {
          nextAppraisal = extractAppraisal(event.output);
        }
        if (!nextSelection && !nextAppraisal) {
          nextComparison = extractComparison(event.output);
        }
        if (!nextSelection && !nextAppraisal && !nextComparison) {
          nextProducts = extractProducts(event.output);
          nextProductsStepId = event.id;
        }
      }

      state = reduceAgentEvent(state, event, {
        hasProducts:
          nextProducts.length > 0 ||
          Boolean(nextComparison) ||
          Boolean(nextSelection) ||
          Boolean(nextAppraisal),
      });
      snapshot = applyRunStateToDetail(snapshot, assistantMessageId, state);
      if (nextProducts.length > 0) {
        snapshot = {
          ...snapshot,
          products: mergeProducts(snapshot.products, nextProducts, nextProductsStepId ?? ""),
        };
      }
      if (nextComparison) {
        const base = replaceComparison ? null : snapshot.comparison;
        replaceComparison = false;
        snapshot = {
          ...snapshot,
          comparison: mergeComparison(base, nextComparison),
        };
      }
      if (nextSelection) {
        // 直接替换、不与上一轮合并：候选分是平台内归一出来的，两轮的分不同尺，
        // 叠在一起会被当成同一把尺量出来的东西。
        snapshot = { ...snapshot, selection: nextSelection };
      }
      if (nextAppraisal) {
        // 同上，直接替换：换一批同款就是换了参照系，两轮的价差不能叠。
        snapshot = { ...snapshot, appraisal: nextAppraisal };
      }
      schedulePublish();
    },
    settle: () => {
      if (!state.completed) state = reduceAgentEvent(state, { type: "runCompleted", exitCode: 0 });
      cancelPublish();
      publish();
    },
    fail: (message) => {
      state = reduceAgentEvent(state, { type: "error", message });
      state = reduceAgentEvent(state, { type: "runCompleted", exitCode: 1 });
      cancelPublish();
      publish();
    },
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

/** 用户主动 detach / cancel 打断的流 —— 不该被当成掉线去重试。 */
function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

/**
 * 这次断流还值得续传吗。
 *
 * 只在「run 确实在服务端起了」（已收到过事件）、「不是被自己掐的」、「不是 404
 * （run 已结束并被回收）」时才重试 —— 否则只是反复撞同一堵墙。
 */
function canReconnect(err: unknown, fold: RunFold, attempt: number): boolean {
  if (attempt > RECONNECT_BACKOFF_MS.length) return false;
  if (fold.stopped() || fold.completed() || fold.lastSeq() <= 0) return false;
  if (isAbort(err)) return false;
  return !(err instanceof AgentStreamError && err.status === 404);
}

/**
 * 驱动一轮运行直到收尾。
 *
 * `reconnect` 给的是同一 run 的续传入口：网络抖动把流掐断时服务端还在跑，
 * 接着已折叠到的 seq 继续看即可 —— 不是重跑，已上屏的内容不会重来。
 */
function driveRun(
  first: AgentRunHandle,
  fold: RunFold,
  reconnect?: () => AgentRunHandle,
): SendHandle {
  let handle = first;

  const promise = (async () => {
    for (let attempt = 0; ; attempt += 1) {
      try {
        await handle.done;
        fold.settle();
        return fold.snapshot();
      } catch (err) {
        // 只是不看这一轮了（离开页面），不是失败：留一份快照给调用方即可。
        if (fold.stopped()) return fold.snapshot();
        const next = attempt + 1;
        if (!reconnect || !canReconnect(err, fold, next)) {
          fold.fail(err instanceof Error ? err.message : "Agent 执行失败");
          throw err;
        }
        await sleep(RECONNECT_BACKOFF_MS[attempt] ?? 0);
        if (fold.stopped()) return fold.snapshot();
        handle = reconnect();
      }
    }
  })();

  return {
    runId: first.runId,
    promise,
    detach: () => {
      fold.stop();
      handle.detach();
    },
    cancel: async () => {
      fold.stop();
      await handle.cancel();
    },
  };
}

/**
 * 发起一次运行。
 *
 * 空消息不会真的发请求：返回一个立即完成的句柄，调用方照常 await。
 */
export function send(
  detail: AgentWorkDetailView,
  payload: ComposerSubmitPayload,
  onUpdate: SendUpdate,
): SendHandle {
  const message = payload.message.trim();
  if (!message) {
    return {
      runId: "empty",
      promise: Promise.resolve(detail),
      detach: () => undefined,
      cancel: async () => undefined,
    };
  }

  const runtimeId = (payload.agent_id || detail.composer_agent_id || "dingda").trim();

  // 先把用户消息与一条空的助手消息塞进 detail，再等 SSE 推进 —— 让用户立刻看到自己发的内容。
  const { detail: optimistic, assistantMessageId } = createOptimisticSendDetail(
    detail,
    message,
    runtimeId,
    payload.model_id,
  );
  const fold = createRunFold(optimistic, assistantMessageId, onUpdate);
  // 首帧之前的空档先垫一句，第一个事件一到就被阶段映射覆盖。
  onUpdate(
    { ...optimistic, status: { ...optimistic.status, hint: `${runtimeId} 启动中…` } },
    "starting",
  );

  const handle = startAgentRunWithEvents(
    {
      runtimeId,
      prompt: message,
      workId: detail.work_id,
      modelId: payload.model_id,
      platformHint: payload.crawl_platform ?? null,
      // 把叮答侧历史交给服务端压缩注入：前端只负责裁剪长度。
      contextMessages: buildContextMessages(detail.messages),
    },
    fold.fold,
    fold.noteSeq,
  );

  return driveRun(handle, fold, () =>
    resumeAgentRun(handle.runId, fold.lastSeq(), fold.fold, fold.noteSeq),
  );
}

/**
 * 接回一次仍在服务端跑的运行。
 *
 * 冷接回（刚进页面 / 刷新）从 0 整条重建：`textDelta` 是追加型的，把原始事件叠在
 * 已落库的折叠结果上会重复文本，而整轮重放能把那条助手消息精确重建出来 ——
 * 服务端日志只需管当前 run，正是因为这个读法。
 *
 * 商品与比价不用清：商品按 id 去重（且跨轮累积，清了会丢早先几轮的结果），
 * 比价由 `replaceComparisonFirst` 让第一段重放替换掉旧计数。
 */
export function attach(
  detail: AgentWorkDetailView,
  runId: string,
  onUpdate: SendUpdate,
): SendHandle {
  const { detail: rebuilt, assistantMessageId } = rebuildAssistantTail(detail);
  const fold = createRunFold(rebuilt, assistantMessageId, onUpdate, {
    replaceComparisonFirst: true,
  });
  onUpdate({ ...rebuilt, status: { ...rebuilt.status, hint: "接回上次执行…" } }, "starting");

  const handle = resumeAgentRun(runId, 0, fold.fold, fold.noteSeq);
  return driveRun(handle, fold, () =>
    resumeAgentRun(runId, fold.lastSeq(), fold.fold, fold.noteSeq),
  );
}

/**
 * 准备一条待重建的助手消息：清空那轮还没收尾的助手消息（保留 id 与起始时间），
 * 找不到就补一条空的。返回新的 detail 与那条消息的 id。
 *
 * 只重建「看起来还在跑」的那条（时长未落库）。收过尾的消息说明它已经是一份答案，
 * 覆盖它等于抹掉上一轮 —— 宁可新起一条，最坏也只是多一个空壳。
 */
function rebuildAssistantTail(detail: AgentWorkDetailView): {
  detail: AgentWorkDetailView;
  assistantMessageId: string;
} {
  const tail = detail.messages[detail.messages.length - 1];
  const inFlight =
    tail?.role === "assistant" && tail.thinking_duration_sec == null ? tail : null;

  const now = new Date().toISOString();
  const assistant: AgentWorkMessageView = {
    id: inFlight?.id ?? `${detail.work_id}-assistant-${Date.now()}`,
    role: "assistant",
    content: "",
    thinking: "",
    created_at: inFlight?.created_at ?? now,
    thinking_started_at: inFlight?.thinking_started_at ?? now,
    thinking_duration_sec: null,
    steps: [],
    timeline: [],
    children: [],
  };
  const messages = inFlight
    ? detail.messages.map((message) => (message.id === inFlight.id ? assistant : message))
    : [...detail.messages, assistant];

  return {
    detail: { ...detail, messages, can_send: false },
    assistantMessageId: assistant.id,
  };
}
