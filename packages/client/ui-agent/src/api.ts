/**
 * Agent 相关的 Server HTTP API（工作对话持久化）。
 */

import type { AgentWorkDetailView, AgentWorkSummary } from "@v2/contracts/ai-work";
import { api } from "@v2/runtime/http-client";

interface AgentWorkDetailResponse {
  ok?: boolean;
  detail: AgentWorkDetailView;
}

/** 从 SQLite 读取 AI 工作对话；不存在返回 null。 */
export async function fetchAgentWorkDetail(
  workId: string,
  options?: { baseUrl?: string | null },
): Promise<AgentWorkDetailView | null> {
  const { data, response } = await api.get<AgentWorkDetailResponse>(
    `/v1/agent/works/${encodeURIComponent(workId)}`,
    {
      baseUrl: options?.baseUrl,
      fallbackError: "读取工作对话失败",
      allowStatuses: [404],
    },
  );
  if (response.status === 404) return null;
  if (!data?.detail?.work_id) return null;
  return data.detail;
}

interface AgentWorkListResponse {
  ok?: boolean;
  items: AgentWorkSummary[];
}

/** 最近工作列表（首页 / 全部项目）。 */
export async function fetchAgentWorkList(
  options?: { baseUrl?: string | null; limit?: number },
): Promise<AgentWorkSummary[]> {
  const limit = options?.limit ?? 40;
  const { data } = await api.get<AgentWorkListResponse>(`/v1/agent/works?limit=${limit}`, {
    baseUrl: options?.baseUrl,
    fallbackError: "读取最近工作失败",
  });
  return Array.isArray(data?.items) ? data.items : [];
}

/** 把 AI 工作对话快照写入 SQLite。 */
export async function putAgentWorkDetail(
  detail: AgentWorkDetailView,
  options?: { baseUrl?: string | null; keepalive?: boolean },
): Promise<AgentWorkDetailView> {
  const { data } = await api.put<AgentWorkDetailResponse>(
    `/v1/agent/works/${encodeURIComponent(detail.work_id)}`,
    { detail },
    {
      baseUrl: options?.baseUrl,
      keepalive: options?.keepalive,
      skipErrorToast: options?.keepalive ?? false,
      fallbackError: "保存工作对话失败",
    },
  );
  return data?.detail ?? detail;
}
