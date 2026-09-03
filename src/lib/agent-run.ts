import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

import type { AgentEvent, AgentEventEnvelope } from "@/contracts/agent-event";
import { parseAgentEventEnvelope } from "@/contracts/agent-event";

export interface LaunchAgentRunRequest {
  runtimeId: string;
  prompt: string;
  cwd?: string | null;
  modelId?: string | null;
  runId?: string | null;
}

export interface LaunchAgentRunResponse {
  runId: string;
  started: boolean;
}

export function createRunId(): string {
  return `run-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export async function launchAgentRun(
  request: LaunchAgentRunRequest,
): Promise<LaunchAgentRunResponse> {
  if (!isTauri()) {
    throw new Error("launchAgentRun 仅在 Tauri 环境可用");
  }

  const runId = request.runId ?? createRunId();
  const response = await invoke<LaunchAgentRunResponse>("launch_agent_runtime", {
    runtimeId: request.runtimeId,
    prompt: request.prompt,
    cwd: request.cwd ?? null,
    modelId: request.modelId ?? null,
    runId,
  });

  return {
    runId: response.runId ?? runId,
    started: response.started ?? true,
  };
}

export async function cancelAgentRun(runId: string): Promise<void> {
  if (!isTauri()) return;
  await invoke("cancel_agent_runtime", { runId });
}

export async function subscribeAgentEvents(
  runId: string,
  onEvent: (event: AgentEvent) => void,
): Promise<UnlistenFn> {
  if (!isTauri()) {
    return () => undefined;
  }

  return listen<AgentEventEnvelope>("agent-event", (message) => {
    const envelope = parseAgentEventEnvelope(message.payload);
    if (!envelope || envelope.runId !== runId) return;

    const { runId: _ignored, ...event } = envelope;
    onEvent(event as AgentEvent);
  });
}

/** 订阅 → 启动 → 等待 runCompleted。 */
export async function runAgentWithEvents(
  request: LaunchAgentRunRequest,
  onEvent: (event: AgentEvent) => void,
): Promise<{ runId: string; exitCode: number }> {
  const runId = request.runId ?? createRunId();

  return new Promise((resolve, reject) => {
    let unlisten: UnlistenFn | null = null;

    const cleanup = () => {
      unlisten?.();
      unlisten = null;
    };

    void subscribeAgentEvents(runId, (event) => {
      onEvent(event);
      if (event.type === "runCompleted") {
        cleanup();
        resolve({ runId, exitCode: event.exitCode });
      }
    })
      .then((fn) => {
        unlisten = fn;
        return launchAgentRun({ ...request, runId });
      })
      .catch((error: unknown) => {
        cleanup();
        reject(error);
      });
  });
}
