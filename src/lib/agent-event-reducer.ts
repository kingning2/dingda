/**
 * 把 Agent SSE 事件折叠成助手消息状态。
 * 步骤块（kind / page / status）只接受后端下发的 step / page，前端不猜。
 * timeline 按事件到达顺序交错（思考 ↔ 工具 ↔ 正文），与服务端日志一致。
 */

import type { AgentEvent } from "@v2/contracts/agent-event";
import type {
  AgentWorkDetailView,
  AgentWorkMessageView,
  AgentWorkStepView,
  AgentWorkTimelineEntry,
} from "@v2/contracts/ai-work";
import { AGENT_RUN_PHASE_MAP, type AgentRunPhase } from "@/lib/agent-run-phase";

export interface AgentRunMessageState {
  /** 前端运行阶段，由 SSE 事件推进。 */
  phase: AgentRunPhase;
  content: string;
  thinking: string;
  steps: AgentWorkStepView[];
  timeline: AgentWorkTimelineEntry[];
  error: string | null;
  completed: boolean;
  /** 本轮 SSE 下发的 CLI session / thread id。 */
  sessionId: string | null;
}

export function createAgentRunMessageState(): AgentRunMessageState {
  return {
    phase: "starting",
    content: "",
    thinking: "",
    steps: [],
    timeline: [],
    error: null,
    completed: false,
    sessionId: null,
  };
}

/** 追加思考/正文片段：连续同 kind 合并，否则新开一段。 */
function appendTextSegment(
  timeline: AgentWorkTimelineEntry[],
  kind: "thinking" | "text",
  chunk: string,
): AgentWorkTimelineEntry[] {
  const last = timeline[timeline.length - 1];
  if (last?.kind === kind) {
    return [...timeline.slice(0, -1), { ...last, text: last.text + chunk }];
  }
  return [...timeline, { kind, id: `${kind}-${timeline.length}`, text: chunk }];
}

/** 工具步骤入时间线；同 id 不重复。browser-live 被真实工具接管时改写 id。 */
function appendStepSegment(
  timeline: AgentWorkTimelineEntry[],
  stepId: string,
  replaceLiveId?: string,
): AgentWorkTimelineEntry[] {
  let next = timeline;
  if (replaceLiveId) {
    next = next.map((entry) =>
      entry.kind === "step" && entry.id === replaceLiveId ? { kind: "step", id: stepId } : entry,
    );
  }
  if (next.some((entry) => entry.kind === "step" && entry.id === stepId)) return next;
  return [...next, { kind: "step", id: stepId }];
}

const STEP_RUNNING: AgentWorkStepView["status"] = {
  state: "running",
  label: "执行中",
  hint: null,
  badge_class: "bg-sky-500/15 text-sky-700",
};

const STEP_DONE: AgentWorkStepView["status"] = {
  state: "ready",
  label: "已完成",
  hint: null,
  badge_class: "bg-emerald-500/15 text-emerald-600",
};

function upsertStep(steps: AgentWorkStepView[], step: AgentWorkStepView): AgentWorkStepView[] {
  const idx = steps.findIndex((item) => item.id === step.id);
  if (idx < 0) return [...steps, step];
  const next = [...steps];
  next[idx] = { ...next[idx], ...step, page: step.page ?? next[idx].page };
  return next;
}

function patchStep(
  steps: AgentWorkStepView[],
  id: string,
  patch: Partial<AgentWorkStepView> & { page_loading?: boolean },
): AgentWorkStepView[] {
  return steps.map((step) => {
    if (step.id !== id) return step;
    const page =
      step.page && patch.page_loading === false
        ? { ...step.page, loading: false }
        : (patch.page ?? step.page);
    const { page_loading: _, ...rest } = patch;
    return { ...step, ...rest, page };
  });
}

export function reduceAgentEvent(
  state: AgentRunMessageState,
  event: AgentEvent,
  options?: { hasProducts?: boolean },
): AgentRunMessageState {
  switch (event.type) {
    case "runStarted":
      return { ...state, phase: "starting" };
    case "textDelta":
      if (!event.text) return state;
      return {
        ...state,
        phase: "outputting",
        content: state.content + event.text,
        timeline: appendTextSegment(state.timeline, "text", event.text),
      };
    case "thinking":
      if (!event.text) return state;
      return {
        ...state,
        phase: "thinking",
        thinking: state.thinking + event.text,
        timeline: appendTextSegment(state.timeline, "thinking", event.text),
      };
    case "toolCall": {
      const incoming =
        event.step?.id
          ? event.step
          : event.id && event.name
            ? {
                id: event.id,
                label: event.name,
                kind: "tool" as const,
                status: STEP_RUNNING,
              }
            : null;
      if (!incoming) return state;

      let steps = [...state.steps];
      let step = { ...incoming };
      let replacedLive = false;

      // OpenCode 常在工具结束后才发 tool_use：直播帧先落在 browser-live，这里挪到对应工具下
      if (step.kind === "browser_crawl" || step.id) {
        const liveIdx = steps.findIndex((item) => item.id === "browser-live");
        if (liveIdx >= 0 && steps[liveIdx]?.page?.screenshot_url) {
          const live = steps[liveIdx];
          step = {
            ...step,
            kind: "browser_crawl",
            label: step.label || live.label,
            hint: step.hint ?? live.hint,
            page: live.page,
            status: step.status?.state === "running" ? step.status : STEP_RUNNING,
          };
          steps = steps.filter((_, index) => index !== liveIdx);
          replacedLive = true;
        }
      }

      return {
        ...state,
        phase: "executing",
        steps: upsertStep(steps, step),
        timeline: appendStepSegment(
          state.timeline,
          step.id,
          replacedLive ? "browser-live" : undefined,
        ),
      };
    }
    case "toolResult": {
      // 商品结果不是后端事件类型，由调用方解析后显式推进到 products 阶段。
      const phase = options?.hasProducts ? "products" : "executing";
      if (event.step?.id) {
        return {
          ...state,
          phase,
          steps: patchStep(state.steps, event.step.id, event.step),
        };
      }
      if (!event.id) return state;
      return {
        ...state,
        phase,
        steps: patchStep(state.steps, event.id, {
          status: STEP_DONE,
          page_loading: false,
        }),
      };
    }
    case "browserFrame": {
      const page = event.page ?? {
        url: event.url,
        title: event.title,
        focus_label: event.hint ?? null,
        loading: true,
        screenshot_url: event.screenshot_url,
      };
      if (!page.screenshot_url) return state;
      // OpenCode 工具完成前不发 tool_use：帧会先到，需合成直播步骤
      let idx = state.steps.findIndex(
        (step) => step.kind === "browser_crawl" && step.status.state === "running",
      );
      if (idx < 0) {
        idx = state.steps.findIndex((step) => step.id === "browser-live");
      }
      const steps = [...state.steps];
      let timeline = state.timeline;
      if (idx < 0) {
        steps.push({
          id: "browser-live",
          label: page.title || "浏览器直播",
          hint: page.focus_label ?? null,
          kind: "browser_crawl",
          status: STEP_RUNNING,
          page,
        });
        timeline = appendStepSegment(timeline, "browser-live");
      } else {
        const prev = steps[idx];
        steps[idx] = {
          ...prev,
          label: page.title || prev.label,
          hint: page.focus_label ?? prev.hint,
          kind: "browser_crawl",
          status: prev.status.state === "running" ? prev.status : STEP_RUNNING,
          page,
        };
      }
      return { ...state, phase: "live", steps, timeline };
    }
    case "fileChanged":
      return state;
    case "session": {
      const sid = event.sessionId?.trim();
      if (!sid) return state;
      return { ...state, sessionId: sid };
    }
    case "error":
      if (!event.message) return state;
      {
        const suffix = `\n\n[错误] ${event.message}`;
        const errOnly = `[错误] ${event.message}`;
        return {
          ...state,
          phase: "failed",
          error: event.message,
          content: state.content ? `${state.content}${suffix}` : errOnly,
          timeline: appendTextSegment(
            state.timeline,
            "text",
            state.content ? suffix : errOnly,
          ),
        };
      }
    case "runCompleted": {
      const steps = state.steps.map((step) =>
        step.status.state === "running"
          ? {
              ...step,
              status: STEP_DONE,
              page: step.page ? { ...step.page, loading: false } : step.page,
            }
          : step,
      );
      // CLI 非 0 退出且没发过 error 事件时，也要让用户看到失败，而不是静默「已完成」
      if (event.exitCode !== 0 && !state.error) {
        const message = `Agent 异常退出（exitCode=${event.exitCode}）`;
        const errOnly = `[错误] ${message}`;
        return {
          ...state,
          phase: "failed",
          error: message,
          content: state.content ? `${state.content}\n\n${errOnly}` : errOnly,
          timeline: appendTextSegment(
            state.timeline,
            "text",
            state.content ? `\n\n${errOnly}` : errOnly,
          ),
          steps,
          completed: true,
        };
      }
      return {
        ...state,
        phase: state.error ? "failed" : "completed",
        steps,
        completed: true,
      };
    }
    default:
      return state;
  }
}

export function applyRunStateToAssistantMessage(
  message: AgentWorkMessageView,
  state: AgentRunMessageState,
): AgentWorkMessageView {
  const startedAt = message.thinking_started_at ?? message.created_at;
  let thinking_duration_sec = message.thinking_duration_sec ?? null;
  if (state.completed && thinking_duration_sec == null && startedAt) {
    const start = Date.parse(startedAt);
    if (!Number.isNaN(start)) {
      thinking_duration_sec = Math.max(0, Math.floor((Date.now() - start) / 1000));
    }
  }

  return {
    ...message,
    content: state.content,
    thinking: state.thinking || null,
    thinking_started_at: startedAt,
    thinking_duration_sec,
    steps: state.steps.length > 0 ? state.steps : message.steps,
    timeline: state.timeline.length > 0 ? state.timeline : message.timeline,
  };
}

export function applyRunStateToDetail(
  detail: AgentWorkDetailView,
  assistantMessageId: string,
  state: AgentRunMessageState,
): AgentWorkDetailView {
  const messages = detail.messages.map((message) =>
    message.id === assistantMessageId
      ? applyRunStateToAssistantMessage(message, state)
      : message,
  );

  const phaseView = AGENT_RUN_PHASE_MAP[state.phase];
  const status = {
    state: phaseView.statusState,
    label: phaseView.label,
    hint: state.phase === "failed" ? state.error : phaseView.hint,
    badge_class: phaseView.badgeClass,
  };

  const crawl = [...state.steps]
    .reverse()
    .find((step) => step.kind === "browser_crawl" && step.page?.screenshot_url);

  const browser_live = crawl?.page
    ? {
        ...detail.browser_live,
        frame_id: crawl.id,
        url: crawl.page.url,
        title: crawl.page.title,
        progress_hint: crawl.page.focus_label ?? null,
        screenshot_url: crawl.page.screenshot_url ?? null,
        focus_label: crawl.page.focus_label ?? null,
        status: {
          state: crawl.status.state,
          label: crawl.status.label,
          hint: crawl.page.focus_label ?? crawl.hint ?? null,
          badge_class: crawl.status.badge_class,
        },
      }
    : detail.browser_live;

  return {
    ...detail,
    messages,
    status,
    can_send: state.completed,
    browser_live,
    ...(state.sessionId
      ? {
          cli_session_id: state.sessionId,
          cli_session_runtime_id: detail.composer_agent_id ?? detail.cli_session_runtime_id ?? null,
        }
      : {}),
  };
}

/** 丢掉某条用户消息及其之后的全部内容，便于从此处重新生成。 */
export function truncateBeforeUserMessage(
  detail: AgentWorkDetailView,
  userMessageId: string,
): AgentWorkDetailView | null {
  const idx = detail.messages.findIndex(
    (message) => message.id === userMessageId && message.role === "user",
  );
  if (idx < 0) return null;
  return {
    ...detail,
    messages: detail.messages.slice(0, idx),
    comparison: null,
    can_send: true,
    // 截断后 CLI 历史对不上，丢掉 session，下一轮当新会话
    cli_session_id: null,
    cli_session_runtime_id: null,
    status: {
      state: "ready",
      label: "已完成",
      hint: null,
      badge_class: "bg-emerald-500/15 text-emerald-600",
    },
  };
}

export function createOptimisticSendDetail(
  detail: AgentWorkDetailView,
  userText: string,
  agentId: string,
  modelId: string | null | undefined,
): { detail: AgentWorkDetailView; assistantMessageId: string } {
  const now = new Date().toISOString();
  const userMessage: AgentWorkMessageView = {
    id: `${detail.work_id}-user-${Date.now()}`,
    role: "user",
    content: userText,
    created_at: now,
  };
  const assistantMessageId = `${detail.work_id}-assistant-${Date.now()}`;
  const assistantMessage: AgentWorkMessageView = {
    id: assistantMessageId,
    role: "assistant",
    content: "",
    thinking: "",
    created_at: now,
    thinking_started_at: now,
    thinking_duration_sec: null,
    steps: [],
    timeline: [],
  };

  const nextTitle =
    detail.messages.length === 0 && userText.trim()
      ? userText.trim().length > 24
        ? `${userText.trim().slice(0, 24)}…`
        : userText.trim()
      : detail.title;

  const sameRuntime =
    Boolean(detail.cli_session_id) &&
    (detail.cli_session_runtime_id ?? detail.composer_agent_id) === agentId;

  return {
    assistantMessageId,
    detail: {
      ...detail,
      title: nextTitle,
      can_send: false,
      comparison: null,
      composer_agent_id: agentId,
      composer_model_id: modelId ?? null,
      // 换 Agent 时丢掉旧 CLI session
      cli_session_id: sameRuntime ? detail.cli_session_id : null,
      cli_session_runtime_id: sameRuntime ? agentId : null,
      status: {
        state: AGENT_RUN_PHASE_MAP.starting.statusState,
        label: AGENT_RUN_PHASE_MAP.starting.label,
        hint: AGENT_RUN_PHASE_MAP.starting.hint,
        badge_class: AGENT_RUN_PHASE_MAP.starting.badgeClass,
      },
      messages: [...detail.messages, userMessage, assistantMessage],
    },
  };
}
