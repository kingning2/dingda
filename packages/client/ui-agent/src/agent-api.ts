/**
 * Agent 相关的 Server HTTP API（偏好 + 工作对话持久化）。
 */

import type {
  AgentDefaultModelView,
  AgentDefaultView,
  AgentPreferencesView,
  AgentRuntimeItem,
  AgentRuntimesCatalogView,
} from "@v2/contracts/agent-runtime";
import type { AgentWorkDetailView } from "@v2/contracts/ai-work";
import { api } from "@v2/runtime/http-client";

interface AgentWorkDetailResponse {
  ok?: boolean;
  detail: AgentWorkDetailView;
}

/** 读取默认 Agent + 各 Agent 默认模型。 */
export async function fetchAgentPreferences(
  options?: { baseUrl?: string | null },
): Promise<AgentPreferencesView> {
  const { data } = await api.get<AgentPreferencesView>("/v1/agent/preferences", {
    baseUrl: options?.baseUrl,
    fallbackError: "读取 Agent 偏好失败",
  });
  return {
    ok: data.ok,
    default_agent_id: data.default_agent_id?.trim() || null,
    default_models: data.default_models ?? {},
  };
}

/** 把默认 Agent 写入 SQLite。 */
export async function putDefaultAgentId(
  agentId: string,
  options?: { baseUrl?: string | null },
): Promise<string> {
  const { data } = await api.put<AgentDefaultView>(
    "/v1/agent/default",
    { agent_id: agentId },
    {
      baseUrl: options?.baseUrl,
      fallbackError: "保存默认 Agent 失败",
    },
  );
  const saved = data.default_agent_id?.trim();
  if (!saved) {
    throw new Error("保存默认 Agent 失败：服务未返回 id");
  }
  return saved;
}

/** 写入某 Agent 的默认模型。 */
export async function putDefaultModelId(
  agentId: string,
  modelId: string,
  options?: { baseUrl?: string | null },
): Promise<AgentDefaultModelView> {
  const { data } = await api.put<AgentDefaultModelView>(
    "/v1/agent/default-model",
    { agent_id: agentId, model_id: modelId },
    {
      baseUrl: options?.baseUrl,
      fallbackError: "保存默认模型失败",
    },
  );
  return data;
}

/** 读取上次扫描落库的 Agent CLI 目录。 */
export async function fetchAgentRuntimesCatalog(
  options?: { baseUrl?: string | null },
): Promise<AgentRuntimeItem[]> {
  const { data } = await api.get<AgentRuntimesCatalogView>("/v1/agent/runtimes", {
    baseUrl: options?.baseUrl,
    fallbackError: "读取 Agent 扫描缓存失败",
  });
  return Array.isArray(data.agents) ? data.agents : [];
}

/** 手动扫描完成后写入 Agent CLI 目录（含模型）。 */
export async function putAgentRuntimesCatalog(
  agents: AgentRuntimeItem[],
  options?: { baseUrl?: string | null },
): Promise<AgentRuntimeItem[]> {
  const { data } = await api.put<AgentRuntimesCatalogView>(
    "/v1/agent/runtimes",
    { agents },
    {
      baseUrl: options?.baseUrl,
      fallbackError: "保存 Agent 扫描结果失败",
    },
  );
  return Array.isArray(data.agents) ? data.agents : agents;
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

export interface AgentWorkSummary {
  work_id: string;
  title: string;
  updated_at: number;
  status_label?: string | null;
  status_state?: string | null;
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
