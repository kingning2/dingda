/**
 * Agent 相关的 Server HTTP API（工作对话持久化）。
 */

import type { AgentWorkDetailView, AgentWorkSummary } from "@v2/contracts/ai-work";
import { api } from "@v2/runtime/http-client";

interface AgentWorkDetailResponse {
  ok?: boolean;
  detail: AgentWorkDetailView;
}

/** 在跑的 run 探针响应（与 Python 侧 `AgentActiveRunView` 对齐）。 */
interface AgentActiveRunResponse {
  ok?: boolean;
  work_id?: string;
  run_id?: string | null;
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

/**
 * 某个工作对话下是否还有 run 在服务端跑；返回它的 run_id，没有则 null。
 *
 * 进页面时用它区分「上次执行已中断」与「服务端还在跑，接回去看直播」。
 * 探针读不到（旧服务端 / 网络抖动）一律按「没有在跑」处理，退回本地快照那条路。
 */
export async function fetchActiveAgentRun(
  workId: string,
  options?: { baseUrl?: string | null },
): Promise<string | null> {
  const { data } = await api.get<AgentActiveRunResponse>(
    `/v1/agent/works/${encodeURIComponent(workId)}/active-run`,
    {
      baseUrl: options?.baseUrl,
      skipErrorToast: true,
      fallbackError: "查询在跑任务失败",
    },
  );
  return data?.run_id ?? null;
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
