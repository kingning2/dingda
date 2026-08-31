/**
 * 任务副驾 IPC — 经 Rust pipe 中转（不经 HTTP 直连 Python）。
 */

import { call } from "./invoke";

export interface CopilotRunStartParams {
  threadId?: string;
  runId?: string;
  messages: Array<{ id: string; role: "user" | "assistant"; content: string }>;
  state?: Record<string, unknown>;
}

export interface CopilotRunStartResult {
  runId: string;
  threadId: string;
}

/** sidecar 管道就绪即可使用副驾。 */
export function copilotReady(): Promise<boolean> {
  return call<boolean>("copilot_ready");
}

/** 启动一轮副驾对话；事件经 `listenCopilotAgui` 接收。 */
export function copilotRunStart(params: CopilotRunStartParams): Promise<CopilotRunStartResult> {
  return call<CopilotRunStartResult>("copilot_run_start", { request: params });
}

/** 取消指定副驾对话轮。 */
export function copilotRunAbort(runId: string): Promise<void> {
  return call<void>("copilot_run_abort", { request: { runId } });
}
