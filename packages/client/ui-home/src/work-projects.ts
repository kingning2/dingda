/**
 * 把 Agent 工作摘要映射成首页「最近项目」卡片数据。
 */

import type { AgentWorkSummary } from "@v2/contracts/ai-work";
import type { Project } from "./mock-data";

function formatUpdatedAt(ts: number): string {
  if (!Number.isFinite(ts) || ts <= 0) return "";
  // 后端存的是 unix 秒
  const ms = ts > 1e12 ? ts : ts * 1000;
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${day} ${hh}:${mm}`;
}

/** 工作摘要 → 项目卡片。 */
export function workSummaryToProject(item: AgentWorkSummary): Project {
  const running = item.status_state === "running" || item.status_state === "browsing";
  return {
    id: item.work_id,
    name: item.title?.trim() || item.work_id,
    updatedAt: formatUpdatedAt(item.updated_at),
    kind: "app",
    status: running ? "draft" : item.status_state === "ready" ? "published" : "draft",
  };
}

export function workSummariesToProjects(items: AgentWorkSummary[]): Project[] {
  return items.map(workSummaryToProject);
}
