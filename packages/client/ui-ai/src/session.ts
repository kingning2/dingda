/**
 * 工作页会话：本地 draft/snapshot + 从 SQLite 加载详情。
 *
 * - draft：首页提交 → 进入工作页之间的首条中转
 * - snapshot：对话快照同步备份（Ctrl+R 兜底）
 * 真相源仍是 SQLite（/v1/agent/works）
 */

import type { AgentWorkDetailView, AgentWorkStatusView } from "@v2/contracts/ai-work";
import type { ComposerSubmitPayload } from "@v2/contracts/composer";
import {
  getComposerAgentOptions,
  resolveDefaultAgentId,
} from "@v2/ui-composer/composer-agents";
import { fetchAgentWorkDetail } from "@v2/ui-agent/agent-api";

const WORK_DRAFT_PREFIX = "dingda:work-draft:";
const WORK_SNAPSHOT_PREFIX = "dingda:work-snapshot:";

function draftKey(workId: string): string {
  return `${WORK_DRAFT_PREFIX}${workId}`;
}

function snapshotKey(workId: string): string {
  return `${WORK_SNAPSHOT_PREFIX}${workId}`;
}

/** 首页提交后暂存首条消息，进入工作页再消费。 */
export function stashWorkDraft(workId: string, draft: ComposerSubmitPayload): void {
  try {
    sessionStorage.setItem(draftKey(workId), JSON.stringify(draft));
  } catch {
    // sessionStorage may be unavailable
  }
}

/** @deprecated 使用 stashWorkDraft */
export function stashWorkPrompt(workId: string, prompt: string): void {
  stashWorkDraft(workId, {
    message: prompt,
    agent_id: resolveDefaultAgentId(getComposerAgentOptions()) ?? "codex",
    attachments: [],
  });
}

/** 只读草稿，不删除（避免 Strict Mode 双挂载把首条吃掉）。 */
export function peekWorkDraft(workId: string): ComposerSubmitPayload | null {
  try {
    const value = sessionStorage.getItem(draftKey(workId));
    if (!value) return null;
    return JSON.parse(value) as ComposerSubmitPayload;
  } catch {
    return null;
  }
}

export function clearWorkDraft(workId: string): void {
  try {
    sessionStorage.removeItem(draftKey(workId));
  } catch {
    // ignore
  }
}

export function stashWorkSnapshot(detail: AgentWorkDetailView): void {
  try {
    sessionStorage.setItem(snapshotKey(detail.work_id), JSON.stringify(detail));
  } catch {
    // quota / private mode
  }
}

export function peekWorkSnapshot(workId: string): AgentWorkDetailView | null {
  try {
    const value = sessionStorage.getItem(snapshotKey(workId));
    if (!value) return null;
    const parsed = JSON.parse(value) as AgentWorkDetailView;
    if (!parsed?.work_id || !Array.isArray(parsed.messages)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearWorkSnapshot(workId: string): void {
  try {
    sessionStorage.removeItem(snapshotKey(workId));
  } catch {
    // ignore
  }
}

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

/** 真实工作区空壳。 */
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
    comparison: null,
    browser_live: {
      frame_id: null,
      url: "about:blank",
      title: "等待任务",
      status: status("idle", "待命", "bg-muted text-muted-foreground"),
      progress_hint: null,
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
  pendingSend: ComposerSubmitPayload | null;
}

/** 同 work 并发 load 共用一个 Promise，避免 Strict Mode 打两次 GET。 */
const inflightLoads = new Map<string, Promise<AgentWorkLoadResult>>();

/**
 * 加载 AI 工作。顺序：SQLite → session 快照 → 首页草稿 → 空壳。
 */
export async function loadAgentWorkDetail(workId: string): Promise<AgentWorkLoadResult> {
  const existing = inflightLoads.get(workId);
  if (existing) return existing;

  const pending = loadAgentWorkDetailOnce(workId).finally(() => {
    if (inflightLoads.get(workId) === pending) {
      inflightLoads.delete(workId);
    }
  });
  inflightLoads.set(workId, pending);
  return pending;
}

async function loadAgentWorkDetailOnce(workId: string): Promise<AgentWorkLoadResult> {
  const seedDraft = peekWorkDraft(workId);
  const localSnapshot = peekWorkSnapshot(workId);

  let saved: AgentWorkDetailView | null = null;
  try {
    saved = await fetchAgentWorkDetail(workId);
  } catch {
    // 读库失败则走本地
  }

  const savedMessages = saved?.messages?.length ?? 0;
  const localMessages = localSnapshot?.messages?.length ?? 0;

  if (saved && savedMessages > 0) {
    if (seedDraft) clearWorkDraft(workId);
    return {
      detail: recoverInterruptedRun(hydrateComposerAgents(saved)),
      pendingSend: null,
    };
  }

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
