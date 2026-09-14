/**
 * 拉起 CLI 登录（桌面走 Tauri invoke）。
 *
 * 职责：封装 `login_agent_runtime` invoke，失败不抛错，以 `started=false` 返回。
 */

import type { AgentRuntimeLoginResult } from "@v2/contracts/agent-runtime";
import { supportsExternalAgents } from "@v2/runtime/capabilities";

/**
 * 拉起 CLI 登录。
 *
 * 不抛错：失败以 `started=false` + 给用户看的 message 返回，调用方直接展示即可。
 */
export async function loginAgentRuntime(agentId: string): Promise<AgentRuntimeLoginResult> {
  if (!supportsExternalAgents()) {
    return { started: false, message: "登录仅在桌面端可用" };
  }
  const { invoke } = await import("@tauri-apps/api/core");
  try {
    return await invoke<AgentRuntimeLoginResult>("login_agent_runtime", { agentId });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { started: false, message };
  }
}
