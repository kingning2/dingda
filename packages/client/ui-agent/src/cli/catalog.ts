/**
 * 拉取本地 Agent 目录（Tauri PATH 探测）与注册表占位。
 *
 * 职责：
 *   - `listAgentRuntimes`：探测 PATH 里的 Agent，并叠上 SQLite 偏好。
 *   - `listAgentRegistryPlaceholders`：仅取注册表占位（不扫 PATH），全部「未安装」。
 */

import type { AgentListResponse } from "@v2/contracts/agent-runtime";
import { supportsExternalAgents } from "@v2/runtime/capabilities";
import { fetchAgentPreferences } from "../api";
import { applyAgentPreferences, normalizeAgentRuntimeItem } from "./normalize";
import type { RawAgentRuntimeItem } from "./normalize";

/**
 * 拉取本地 Agent 目录（Tauri PATH 探测）。
 * 若传入 apiBaseUrl，会再读 SQLite 偏好，并盖到 is_default / preferred_model_id。
 */
export async function listAgentRuntimes(
  apiBaseUrl?: string | null,
): Promise<import("@v2/contracts/agent-runtime").AgentRuntimeItem[]> {
  if (!supportsExternalAgents()) return [];

  const { invoke } = await import("@tauri-apps/api/core");
  const response = await invoke<AgentListResponse>("list_agent_runtimes_command");
  const agents = response.agents.map((agent) =>
    normalizeAgentRuntimeItem(agent as RawAgentRuntimeItem),
  );

  if (!apiBaseUrl) return agents;

  try {
    const preferences = await fetchAgentPreferences({ baseUrl: apiBaseUrl });
    return applyAgentPreferences(agents, preferences);
  } catch {
    return agents;
  }
}

/**
 * 仅取注册表占位（不扫 PATH），全部为「未安装」。
 * 用于尚未手动扫描、库中无缓存时的首屏展示。
 */
export async function listAgentRegistryPlaceholders(): Promise<
  import("@v2/contracts/agent-runtime").AgentRuntimeItem[]
> {
  if (!supportsExternalAgents()) return [];
  const { invoke } = await import("@tauri-apps/api/core");
  const response = await invoke<AgentListResponse>("list_agent_registry_command");
  return response.agents.map((agent) =>
    normalizeAgentRuntimeItem(agent as RawAgentRuntimeItem),
  );
}
