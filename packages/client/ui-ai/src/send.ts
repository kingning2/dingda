/**
 * 发起一次 Agent 运行，并把 SSE 事件折进 detail。
 *
 * 职责：
 *   从「用户按下发送」到「运行结束」的全过程：乐观插入消息 → 起 SSE → 每个事件
 *   更新一份新的 AgentWorkDetailView 交给调用方 → 结束/失败时收尾。
 *
 * 设计说明：
 *   - 本模块只做编排与状态推进；「工具输出 → 商品/比价视图」的解析在 agent-output.ts。
 *   - 前端**不猜**后端语义：`hasProducts` 由这里解析出结果后显式告知 reducer，
 *     因为「商品结果」不是后端的事件类型。
 *   - 换 Agent 时丢掉旧 CLI session：历史对不上，继续用会串上下文。
 *   - 冷启动（无 session）时把叮答侧历史交给服务端压缩注入，前端只负责裁剪长度。
 */

import type { ComposerSubmitPayload } from "@v2/contracts/composer";
import type {
  AgentWorkComparisonView,
  AgentWorkDetailView,
  AgentWorkMessageView,
} from "@v2/contracts/ai-work";
import type { CrawlProductItem } from "@v2/contracts/crawler";
import {
  applyRunStateToDetail,
  createAgentRunMessageState,
  createOptimisticSendDetail,
  reduceAgentEvent,
} from "@v2/ui-agent/agent-event-reducer";
import type { AgentRunPhase } from "@v2/ui-agent/agent-run-phase";
import { startAgentRunWithEvents } from "@v2/ui-agent/agent-run";
import { useDiscoveryStore } from "@v2/app-state";
import { extractComparison, extractProducts, mergeComparison, mergeProducts } from "./agent-output";

/** 一次运行的句柄：拿 runId、等结束、主动取消。 */
export interface SendHandle {
  runId: string;
  promise: Promise<AgentWorkDetailView>;
  cancel: () => Promise<void>;
}

/** 运行更新回调：同时返回对话快照和当前前端阶段。 */
export type SendUpdate = (next: AgentWorkDetailView, phase: AgentRunPhase) => void;

/** 注入历史的上限：条数与单条字符数。太长的历史对模型没用，只是浪费上下文。 */
const CONTEXT_MAX_MESSAGES = 30;
const CONTEXT_MAX_CHARS = 2000;

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
 * 发起一次运行。
 *
 * 空消息与「产品 Agent」两种情况下不会真的发请求：前者返回一个立即完成的句柄，
 * 后者返回一个已 reject 的 promise —— 调用方统一用 catch 处理，不必分支。
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
      cancel: async () => undefined,
    };
  }

  const runtimeId = (payload.agent_id || detail.composer_agent_id || "codex").trim();
  if (runtimeId === "dingda" || runtimeId === "product") {
    return {
      runId: "blocked",
      promise: Promise.reject(new Error("产品 Agent 尚未开放，请在设置里选择 Codex / Claude")),
      cancel: async () => undefined,
    };
  }

  // 先把用户消息与一条空的助手消息塞进 detail，再等 SSE 推进 —— 让用户立刻看到自己发的内容。
  const { detail: optimistic, assistantMessageId } = createOptimisticSendDetail(
    detail,
    message,
    runtimeId,
    payload.model_id,
  );
  let snapshot: AgentWorkDetailView = {
    ...optimistic,
    status: { ...optimistic.status, hint: `${runtimeId} 启动中…` },
  };
  let runState = createAgentRunMessageState();
  onUpdate(snapshot, runState.phase);

  // Tauri 扫描到的 CLI 绝对路径；目录里没有就交给服务端按 PATH 找。
  const catalogCommand =
    useDiscoveryStore.getState().agents.find((agent) => agent.id === runtimeId)?.command?.trim() ||
    null;

  const resumeSession =
    snapshot.cli_session_id &&
    (snapshot.cli_session_runtime_id ?? snapshot.composer_agent_id) === runtimeId
      ? snapshot.cli_session_id
      : null;
  // 无 CLI session（含换 Agent）时把叮答侧历史交给服务端压缩注入
  const contextMessages = resumeSession ? null : buildContextMessages(detail.messages);

  const handle = startAgentRunWithEvents(
    {
      runtimeId,
      prompt: message,
      modelId: payload.model_id,
      platformHint: payload.crawl_platform ?? null,
      executable: catalogCommand,
      sessionId: resumeSession,
      contextMessages,
    },
    (event) => {
      // 工具结果先解析一遍：既决定阶段（products / executing），也拿到要并进 detail 的数据。
      let nextProducts: CrawlProductItem[] = [];
      let nextProductsStepId: string | null = null;
      let nextComparison: AgentWorkComparisonView | null = null;
      if (event.type === "toolResult") {
        nextComparison = extractComparison(event.output);
        if (!nextComparison) {
          nextProducts = extractProducts(event.output);
          nextProductsStepId = event.id;
        }
      }

      runState = reduceAgentEvent(runState, event, {
        hasProducts: nextProducts.length > 0 || Boolean(nextComparison),
      });
      snapshot = applyRunStateToDetail(snapshot, assistantMessageId, runState);
      if (nextProducts.length > 0) {
        snapshot = {
          ...snapshot,
          products: mergeProducts(snapshot.products, nextProducts, nextProductsStepId ?? ""),
        };
      }
      if (nextComparison) {
        snapshot = {
          ...snapshot,
          comparison: mergeComparison(snapshot.comparison, nextComparison),
        };
      }
      onUpdate(snapshot, runState.phase);
    },
  );

  const promise = handle.done
    .then(() => {
      // 流意外结束但没收到 runCompleted 时，仍由同一状态机收尾 ——
      // 否则 can_send 会永远停在 false，用户发不出下一句。
      if (!runState.completed) {
        runState = reduceAgentEvent(runState, { type: "runCompleted", exitCode: 0 });
      }
      snapshot = applyRunStateToDetail(snapshot, assistantMessageId, runState);
      onUpdate(snapshot, runState.phase);
      return snapshot;
    })
    .catch((err: unknown) => {
      // 网络或启动错误也要进入 failed，并允许用户继续发送。
      const message = err instanceof Error ? err.message : "Agent 执行失败";
      runState = reduceAgentEvent(runState, { type: "error", message });
      runState = reduceAgentEvent(runState, { type: "runCompleted", exitCode: 1 });
      snapshot = applyRunStateToDetail(snapshot, assistantMessageId, runState);
      onUpdate(snapshot, runState.phase);
      throw err;
    });

  return { runId: handle.runId, promise, cancel: handle.cancel };
}
