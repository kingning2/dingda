/**
 * 工作页本地暂存（sessionStorage）。
 *
 * - draft：仅「首页提交 → 进入工作页」之间的首条草稿中转，不是对话真相源
 * - snapshot：对话完整快照的同步备份；Ctrl+R 时异步 PUT SQLite 常被掐断，靠它兜底
 *
 * 真相源仍是 SQLite（/v1/agent/works）；加载顺序：SQLite → snapshot → draft → 空壳
 */

import type { AgentWorkDetailView } from "@/contracts/ai-work";
import type { ComposerSubmitPayload } from "@/contracts/composer";
import { getComposerAgentOptions, resolveDefaultAgentId } from "@/components/composer/composer-agents";

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
    // sessionStorage may be unavailable in hardened contexts.
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

/** 首条已交给 CLI 后清除草稿。 */
export function clearWorkDraft(workId: string): void {
  try {
    sessionStorage.removeItem(draftKey(workId));
  } catch {
    // ignore
  }
}

/** 同步写入对话快照（Ctrl+R 可立刻读回；不替代 SQLite）。 */
export function stashWorkSnapshot(detail: AgentWorkDetailView): void {
  try {
    sessionStorage.setItem(snapshotKey(detail.work_id), JSON.stringify(detail));
  } catch {
    // quota / private mode
  }
}

/** 读取本地对话快照。 */
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

/** @deprecated 使用 peekWorkDraft + clearWorkDraft */
export function takeWorkDraft(workId: string): ComposerSubmitPayload | null {
  const draft = peekWorkDraft(workId);
  if (draft) clearWorkDraft(workId);
  return draft;
}
