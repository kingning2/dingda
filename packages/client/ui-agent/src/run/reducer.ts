/**
 * 把 Agent SSE 事件折叠成助手消息状态。
 * 步骤块（kind / page / status）只接受后端下发的 step / page，前端不猜。
 * timeline 按事件到达顺序交错（思考 ↔ 工具 ↔ 正文），与服务端日志一致。
 * 子会话（worker）事件走 childEvent 信封，折叠进独立子块，不摊进父的平铺步骤。
 */

import type { AgentEvent } from "@v2/contracts/agent-event";
import type {
  AgentWorkChildView,
  AgentWorkDetailView,
  AgentWorkMessageView,
  AgentWorkStepView,
  AgentWorkStatusView,
  AgentWorkTimelineEntry,
} from "@v2/contracts/ai-work";
import { AGENT_RUN_PHASE_MAP, type AgentRunPhase } from "./phase";
import { STATUS_TONE } from "../status-tone";

/** 扫码登录帧的约定 URL（后端 login 工具推的），与爬取直播帧区分。 */
function isLoginFrameUrl(url: string | null | undefined): boolean {
  return Boolean(url?.startsWith("dingda://login/"));
}

/** 一条助手消息在运行中的完整状态；每来一个 SSE 事件就整体替换一次。 */
export interface AgentRunMessageState {
  /** 前端运行阶段，由 SSE 事件推进。 */
  phase: AgentRunPhase;
  content: string;
  thinking: string;
  steps: AgentWorkStepView[];
  timeline: AgentWorkTimelineEntry[];
  error: string | null;
  completed: boolean;
  /** 本轮派出的子会话（worker）。 */
  children: AgentChildRunState[];
}

/**
 * 一个子会话的运行态。
 *
 * `phase` / `status` 是**服务端**的 AgentPhase（pending/running/needs_repair/…），
 * `run` 是子会话自己的整份前端运行态 —— 直接复用 `reduceAgentEvent` 递归折叠，
 * 于是子会话的步骤、正文、思考、时间线不必另写一套。
 */
export interface AgentChildRunState {
  runId: string;
  role: string;
  label: string;
  phase: string;
  step: string | null;
  summary: string;
  status: AgentWorkStatusView;
  run: AgentRunMessageState;
}

/** 新建一条空的助手消息状态，起始阶段为 starting。 */
export function createAgentRunMessageState(): AgentRunMessageState {
  return {
    phase: "starting",
    content: "",
    thinking: "",
    steps: [],
    timeline: [],
    error: null,
    completed: false,
    children: [],
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
  badge_class: STATUS_TONE.active,
};

const STEP_DONE: AgentWorkStepView["status"] = {
  state: "ready",
  label: "已完成",
  hint: null,
  badge_class: STATUS_TONE.ready,
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

/** 服务端 AgentPhase → 子块状态徽标。 */
function childStatus(phase: string, errorCode?: string | null): AgentWorkStatusView {
  if (phase === "completed") {
    return { state: "ready", label: "已完成", hint: null, badge_class: STATUS_TONE.ready };
  }
  if (phase === "failed" || phase === "cancelled") {
    return {
      state: "error",
      label: phase === "cancelled" ? "已取消" : "失败",
      hint: errorCode ?? null,
      badge_class: STATUS_TONE.failed,
    };
  }
  if (phase === "needs_repair") {
    return {
      state: "pending",
      label: "待修复",
      hint: errorCode ?? null,
      badge_class: STATUS_TONE.pending,
    };
  }
  return { state: "running", label: "执行中", hint: null, badge_class: STATUS_TONE.active };
}

/** 新建一个空子块；内层是一份完整的运行态，直接复用 reducer。 */
function createChildRunState(runId: string, role: string): AgentChildRunState {
  const name = (role || "worker").trim() || "worker";
  return {
    runId,
    role: name,
    label: name === "worker" ? "worker 子会话" : `${name} 子会话`,
    phase: "pending",
    step: null,
    summary: "",
    status: childStatus("pending"),
    run: createAgentRunMessageState(),
  };
}

/** 子块入时间线；同 runId 不重复。 */
function appendChildSegment(
  timeline: AgentWorkTimelineEntry[],
  runId: string,
): AgentWorkTimelineEntry[] {
  if (timeline.some((entry) => entry.kind === "child" && entry.id === runId)) return timeline;
  return [...timeline, { kind: "child", id: runId }];
}

/** 按 runId 找到子块并用 patch 更新；没有则以空子块为底新建。 */
function withChild(
  state: AgentRunMessageState,
  runId: string,
  role: string,
  patch: (child: AgentChildRunState) => AgentChildRunState,
): AgentRunMessageState {
  const key = (runId || "").trim();
  if (!key) return state;
  const idx = state.children.findIndex((item) => item.runId === key);
  if (idx < 0) {
    const children = [...state.children, patch(createChildRunState(key, role))];
    return { ...state, children, timeline: appendChildSegment(state.timeline, key) };
  }
  const children = [...state.children];
  children[idx] = patch(children[idx]);
  return { ...state, children };
}

/** 父会话收尾：仍未收尾的子块标「已中断」，别让界面永远转圈。 */
function settleChildren(children: AgentChildRunState[]): AgentChildRunState[] {
  return children.map((child) => {
    if (
      child.phase === "completed" ||
      child.phase === "failed" ||
      child.phase === "cancelled"
    ) {
      return child;
    }
    return {
      ...child,
      status: {
        state: "pending",
        label: "已中断",
        hint: "父会话已结束，子会话未收尾",
        badge_class: STATUS_TONE.pending,
      },
      run: { ...child.run, completed: true },
    };
  });
}

/**
 * 把单个 SSE 事件折叠进状态，返回新对象（不改原状态）。
 *
 * `hasProducts` 由调用方解析事件后传入：「商品结果」不是后端的事件类型，
 * 前端不猜，只能由知道业务语义的一方显式告知。
 */
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

      // 工具结束后才发 tool_use 时：直播帧先落在 browser-live，这里挪到对应工具下。
      // 登录块不接管 browser-live —— 那是爬取截图，不能糊到扫码卡上。
      if (step.kind !== "login" && (step.kind === "browser_crawl" || step.id)) {
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
      const loginFrame = isLoginFrameUrl(page.url);
      // 帧可以点名挂哪一块：掉线恢复的二维码必须钉在「扫码登录」块上，否则会被
      // 还在跑的搜索块抢走。登录帧优先挂进行中的 login 块；普通帧挂 browser_crawl。
      let idx = event.stepId
        ? state.steps.findIndex((step) => step.id === event.stepId)
        : -1;
      if (idx < 0 && loginFrame) {
        idx = state.steps.findIndex(
          (step) => step.kind === "login" && step.status.state === "running",
        );
      }
      if (idx < 0) {
        // 工具完成前不发 tool_use：帧会先到，需合成直播步骤
        idx = state.steps.findIndex(
          (step) => step.kind === "browser_crawl" && step.status.state === "running",
        );
      }
      if (idx < 0) {
        idx = state.steps.findIndex((step) => step.id === "browser-live");
      }
      const steps = [...state.steps];
      let timeline = state.timeline;
      if (idx < 0) {
        steps.push({
          id: loginFrame ? "login-pending" : "browser-live",
          label: page.title || (loginFrame ? "扫码登录" : "浏览器直播"),
          hint: page.focus_label ?? null,
          kind: loginFrame ? "login" : "browser_crawl",
          status: STEP_RUNNING,
          page,
        });
        timeline = appendStepSegment(timeline, steps[steps.length - 1]!.id);
      } else {
        const prev = steps[idx];
        const keepLogin = prev.kind === "login" || loginFrame;
        steps[idx] = {
          ...prev,
          // 步骤标题优先：后端已按工具还原出「搜索商品 · 闲鱼」这类动作文案，
          // 直播帧的页面标题只该落在 page.title（页卡头部已渲染），不能反过来覆盖它。
          label: prev.label || page.title,
          hint: page.focus_label ?? prev.hint,
          // 登录帧绝不能把 login 块改写成 browser_crawl（否则前端又回到直播页卡）
          kind: keepLogin ? "login" : prev.kind || "browser_crawl",
          status: prev.status.state === "running" ? prev.status : STEP_RUNNING,
          page,
        };
      }
      // 扫码等待不是「浏览器直播」：状态行继续显示 Working，避免 LIVE / Browsing 误导
      return { ...state, phase: loginFrame ? "executing" : "live", steps, timeline };
    }
    case "agentPhase": {
      // 父会话自己不发 agentPhase（只有子会话会推），role=parent 时不建块
      if (event.role === "parent") return state;
      const next = withChild(state, event.runId, event.role, (child) => ({
        ...child,
        phase: event.phase,
        step: event.step ?? child.step,
        summary: event.summary ?? child.summary,
        status: childStatus(event.phase, event.errorCode),
      }));
      return next.phase === "starting" ? { ...next, phase: "executing" } : next;
    }
    case "childEvent": {
      // 子会话事件：递归喂给子块自己的运行态，不写进父的 steps / timeline
      return withChild(state, event.childRunId, event.role, (child) => ({
        ...child,
        run: reduceAgentEvent(child.run, event.event, options),
      }));
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
      // 父 SSE 一关就不会再有子会话事件进来，别让子块永远转圈
      const children = settleChildren(state.children);
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
          children,
          completed: true,
        };
      }
      return {
        ...state,
        phase: state.error ? "failed" : "completed",
        steps,
        children,
        completed: true,
      };
    }
    default:
      return state;
  }
}

/**
 * 把运行态写回助手消息。
 *
 * 思考时长后端不给，只能在完成时按 thinking_started_at 起算补一次。
 */
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
    children: state.children.length > 0 ? state.children.map(toChildView) : message.children,
  };
}

/** 子会话运行态 → 落库视图（内层 run 摊平成步骤 / 时间线 / 正文）。 */
function toChildView(child: AgentChildRunState): AgentWorkChildView {
  return {
    run_id: child.runId,
    role: child.role,
    label: child.label,
    phase: child.phase,
    status: child.status,
    step: child.step,
    steps: child.run.steps,
    timeline: child.run.timeline,
    content: child.run.content,
    thinking: child.run.thinking,
    summary: child.summary,
  };
}

/** 步骤是否是「带截图的爬取步」（直播帧的候选）。 */
function hasCrawlFrame(step: AgentWorkStepView): boolean {
  return step.kind === "browser_crawl" && Boolean(step.page?.screenshot_url);
}

/**
 * 把运行态写回整份详情：消息、全局状态、浏览器直播帧、可发送标志。
 *
 * 直播帧取**最后一个**带截图的 browser_crawl 步骤，这样重进会话还能看到最后一帧，
 * 而不是空白。父自己没在爬时（活都派给 worker 了）回落到最新子块里的帧。
 */
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

  const crawl =
    [...state.steps].reverse().find(hasCrawlFrame) ??
    [...state.children]
      .reverse()
      .flatMap((child) => [...child.run.steps].reverse())
      .find(hasCrawlFrame);

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
    status: {
      state: "ready",
      label: "已完成",
      hint: null,
      badge_class: STATUS_TONE.ready,
    },
  };
}

/**
 * 乐观发送：先把用户消息与一条空的助手消息塞进详情，再等 SSE 推进。
 *
 * 标题只在首轮生成，取用户输入前 24 字。
 */
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

  return {
    assistantMessageId,
    detail: {
      ...detail,
      title: nextTitle,
      can_send: false,
      comparison: null,
      composer_agent_id: agentId,
      composer_model_id: modelId ?? null,
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
