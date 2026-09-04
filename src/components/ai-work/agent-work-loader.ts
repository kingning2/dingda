import type { AgentWorkDetailView, AgentWorkStatusView } from "@/contracts/ai-work";
import type { ComposerSubmitPayload } from "@/contracts/composer";
import {
  getComposerAgentOptions,
  resolveDefaultAgentId,
} from "@/components/composer/composer-agents";
import { fetchAgentWorkDetail } from "@/lib/agent-api";
import {
  peekWorkDraft,
  clearWorkDraft,
  peekWorkSnapshot,
} from "./work-draft";

function status(
  state: string,
  label: string,
  badge_class: string,
  hint?: string | null,
): AgentWorkStatusView {
  return { state, label, badge_class, hint };
}

function titleFromPrompt(prompt: string): string {
  const trimmed = prompt.trim();
  if (!trimmed) return "新任务";
  return trimmed.length > 24 ? `${trimmed.slice(0, 24)}…` : trimmed;
}

function composerFields(agentId?: string | null, modelId?: string | null) {
  const agents = getComposerAgentOptions();
  return {
    composer_agents: agents,
    composer_agent_id: agentId ?? resolveDefaultAgentId(agents),
    composer_model_id: modelId ?? null,
  };
}

function hydrateComposerAgents(detail: AgentWorkDetailView): AgentWorkDetailView {
  const agents = getComposerAgentOptions();
  return {
    ...detail,
    composer_agents: agents,
    composer_agent_id:
      detail.composer_agent_id && agents.some((agent) => agent.id === detail.composer_agent_id)
        ? detail.composer_agent_id
        : resolveDefaultAgentId(agents),
  };
}

/** 刷新时若上次执行中被打断，放开输入并补齐思考秒数。 */
function recoverInterruptedRun(detail: AgentWorkDetailView): AgentWorkDetailView {
  const interrupted = !detail.can_send || detail.status.state === "running";
  if (!interrupted) return detail;

  const messages = detail.messages.map((message) => {
    if (message.role !== "assistant") return message;
    if (message.thinking_duration_sec != null) return message;
    const startedAt = message.thinking_started_at ?? message.created_at;
    const start = Date.parse(startedAt);
    if (Number.isNaN(start)) return message;
    return {
      ...message,
      thinking_started_at: startedAt,
      thinking_duration_sec: Math.max(0, Math.floor((Date.now() - start) / 1000)),
    };
  });

  return {
    ...detail,
    messages,
    can_send: true,
    status: status(
      "ready",
      "已恢复",
      "bg-muted text-muted-foreground",
      "上次执行已中断，对话仍在，可继续提问",
    ),
  };
}

/** 真实工作区空壳（无 demo 数据）。 */
export function buildEmptyWorkDetail(
  workId: string,
  seed?: Pick<ComposerSubmitPayload, "message" | "agent_id" | "model_id"> | null,
): AgentWorkDetailView {
  const seedPrompt = seed?.message?.trim() || null;
  return {
    work_id: workId,
    title: seedPrompt ? titleFromPrompt(seedPrompt) : "新任务",
    status: seedPrompt
      ? status("ready", "就绪", "bg-muted text-muted-foreground", "正在启动任务…")
      : status("ready", "就绪", "bg-muted text-muted-foreground", "输入需求后开始执行"),
    messages: [],
    products: {
      items: [],
      total: 0,
      status: status("idle", "等待抓取", "bg-muted text-muted-foreground"),
    },
    recommendations: {
      items: [],
      total: 0,
      status: status("idle", "待生成", "bg-muted text-muted-foreground"),
      summary: null,
    },
    browser_live: {
      frame_id: null,
      url: "about:blank",
      title: "等待任务",
      status: status("idle", "待命", "bg-muted text-muted-foreground"),
      progress_hint: "Agent 开始执行后，这里会同步当前浏览的网页。",
      focus_label: null,
    },
    browser_history: [],
    composer_placeholder: "补充筛选条件或修改任务…",
    can_send: !seedPrompt,
    cli_session_id: null,
    cli_session_runtime_id: null,
    ...composerFields(seed?.agent_id, seed?.model_id),
  };
}

export interface AgentWorkLoadResult {
  detail: AgentWorkDetailView;
  /** 首页草稿，需由 CLI 发送首条。 */
  pendingSend: ComposerSubmitPayload | null;
}

/**
 * 加载真实 AI 工作。
 * 顺序：SQLite（真相源）→ session 快照（Ctrl+R 兜底）→ 首页草稿 → 空壳。
 */
export async function loadAgentWorkDetail(workId: string): Promise<AgentWorkLoadResult> {
  const seedDraft = peekWorkDraft(workId);
  const localSnapshot = peekWorkSnapshot(workId);

  let saved: AgentWorkDetailView | null = null;
  try {
    saved = await fetchAgentWorkDetail(workId);
  } catch {
    // 读库失败则走本地快照/草稿
  }

  const savedMessages = saved?.messages?.length ?? 0;
  const localMessages = localSnapshot?.messages?.length ?? 0;

  // 库里已有消息：以库为准
  if (saved && savedMessages > 0) {
    if (seedDraft) clearWorkDraft(workId);
    return {
      detail: recoverInterruptedRun(hydrateComposerAgents(saved)),
      pendingSend: null,
    };
  }

  // SQLite 还没写上（常见于 Ctrl+R 打断 PUT），用同步快照恢复
  if (localSnapshot && localMessages > 0) {
    if (seedDraft) clearWorkDraft(workId);
    return {
      detail: recoverInterruptedRun(hydrateComposerAgents(localSnapshot)),
      pendingSend: null,
    };
  }

  if (seedDraft?.message.trim()) {
    return {
      detail: buildEmptyWorkDetail(workId, seedDraft),
      pendingSend: seedDraft,
    };
  }

  if (saved) {
    return {
      detail: recoverInterruptedRun(hydrateComposerAgents(saved)),
      pendingSend: null,
    };
  }

  return {
    detail: buildEmptyWorkDetail(workId),
    pendingSend: null,
  };
}
