/**
 * 下载 Agent 到叮答托管目录（当前仅 OpenCode）。
 *
 * 职责：封装 `download_agent_runtime` invoke，处理 Rust 侧 camelCase 字段回退。
 */

import { supportsExternalAgents } from "@v2/runtime/capabilities";
import type { AgentDownloadResult } from "./normalize";

/** 下载到叮答托管目录。 */
export async function downloadAgentRuntime(agentId: string): Promise<AgentDownloadResult> {
  if (!supportsExternalAgents()) {
    throw new Error("下载仅在桌面端可用");
  }
  const { invoke } = await import("@tauri-apps/api/core");
  // Rust 侧 ManagedDownloadResult 是 camelCase，agentId 是主字段；agent_id 是旧字段兜底。
  const raw = await invoke<{
    agentId?: string;
    agent_id?: string;
    path: string;
    version?: string | null;
    message: string;
  }>("download_agent_runtime", { agentId });

  return {
    agentId: raw.agentId ?? raw.agent_id ?? agentId,
    path: raw.path,
    version: raw.version ?? null,
    message: raw.message,
  };
}
