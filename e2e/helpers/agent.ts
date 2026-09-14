/**
 * Agent 运行时目录 / 偏好 的测试侧辅助。
 *
 * 与 `helpers/account.ts` 同样的定位：跑在**测试进程**里直连被测壳拉起的 Server，
 * 用来在点击前后独立取证 —— **不**用来推进页面流程。
 *
 * 相关接口见 `packages-py/api/src/api/agent.py`：
 *   GET /v1/agent/runtimes      → 上次扫描落库的 CLI 目录（含 models）
 *   GET /v1/agent/preferences   → default_agent_id + default_models
 *   GET /v1/agent/default       → 当前默认 Agent id
 *   PUT /v1/agent/default-model → 写某 Agent 的默认模型
 */

export type AgentRuntimeModel = { id: string; label: string };

export type AgentRuntimeItem = {
  id: string;
  name: string;
  description?: string;
  available: boolean;
  version?: string | null;
  is_default?: boolean;
  auth?: { state: string; label: string; can_login?: boolean } | null;
  models?: AgentRuntimeModel[] | null;
  preferred_model_id?: string | null;
};

export type AgentPreferences = {
  default_agent_id: string;
  default_models: Record<string, string>;
};

async function getJson<T>(port: number, path: string, timeoutMs = 8_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`http://127.0.0.1:${port}${path}`, {
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`GET ${path} 返回 HTTP ${response.status}`);
    return (await response.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

/** 上次扫描落库的 Agent 目录。 */
export async function fetchAgentRuntimes(port: number): Promise<AgentRuntimeItem[]> {
  const payload = await getJson<{ agents?: AgentRuntimeItem[] }>(port, "/v1/agent/runtimes");
  return payload.agents ?? [];
}

/** 默认 Agent 与各 Agent 默认模型。 */
export function fetchAgentPreferences(port: number): Promise<AgentPreferences> {
  return getJson<AgentPreferences>(port, "/v1/agent/preferences");
}

/** 当前默认 Agent id。 */
export async function fetchDefaultAgentId(port: number): Promise<string> {
  const payload = await getJson<{ default_agent_id?: string }>(port, "/v1/agent/default");
  return payload.default_agent_id ?? "";
}

/**
 * 写某 Agent 的默认模型。
 *
 * 正常路径由页面上的下拉触发；这里**只作还原兜底** —— 若往返验证的后半段
 * （把模型改回原值）在 UI 上失败，用它把用户的真实偏好恢复回去。
 */
export async function putDefaultModel(
  port: number,
  agentId: string,
  modelId: string,
): Promise<AgentPreferences["default_models"]> {
  const response = await fetch(`http://127.0.0.1:${port}/v1/agent/default-model`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId, model_id: modelId }),
  });
  if (!response.ok) {
    throw new Error(`PUT /v1/agent/default-model 返回 HTTP ${response.status}`);
  }
  const payload = (await response.json()) as { default_models?: Record<string, string> };
  return payload.default_models ?? {};
}

/**
 * 挑一个适合做「模型切换往返验证」的 Agent。
 *
 * 条件：可用、模型数 ≥2、且**已保存的偏好模型确实还在模型列表里**
 * （否则 UI 会回落到 `models[0]`，无法用 UI 还原原值）。
 * 在满足条件的里面取**模型列表最短**的：下拉项少、无需滚动，点击最稳
 * （opencode 有 374 个模型，DOM 太大）。
 */
export function pickAgentForModelRoundTrip(
  agents: AgentRuntimeItem[],
  defaultModels: Record<string, string>,
): AgentRuntimeItem | null {
  const usable = agents.filter((agent) => {
    const models = agent.models ?? [];
    if (!agent.available || models.length < 2) return false;
    const saved = defaultModels[agent.id];
    return Boolean(saved) && models.some((model) => model.id === saved);
  });

  const pool =
    usable.length > 0
      ? usable
      : agents.filter((agent) => agent.available && (agent.models?.length ?? 0) >= 2);
  if (pool.length === 0) return null;

  return pool.reduce((best, agent) =>
    (agent.models?.length ?? 0) < (best.models?.length ?? 0) ? agent : best,
  );
}
