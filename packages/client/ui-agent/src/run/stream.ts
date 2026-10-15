/**
 * Agent 运行：统一走 Python Server SSE（内置产品 Agent）。
 *
 * 职责：
 *   发起一次 dingda 运行并逐帧转发 SSE 事件给调用方。
 */

import type { AgentEvent } from "@v2/contracts/agent-event";
import { resolveBaseUrl } from "@v2/runtime/http-client";
import { apiPaths } from "@v2/routes/api-paths";

/** 一次运行的入参；字段与后端 `/v1/agent/works/{work_id}/run` 的 body 一一对应。 */
export interface LaunchAgentRunRequest {
  /** 产品 Agent 工作对话 id */
  workId: string;
  prompt: string;
  runId?: string | null;
}

export function createRunId(): string {
  return `run-${Date.now().toString(36)}`;
}

export interface AgentRunHandle {
  runId: string;
  /** 正常结束 resolve（exitCode 来自 runCompleted）；出错 reject。 */
  done: Promise<{ runId: string; exitCode: number }>;
  /** 中断本轮：前端断流（服务端继续跑完并落库，UI 丢弃后续事件）。 */
  cancel: () => Promise<void>;
}

/** 把 SSE data 行还原成事件对象；解析失败返回 null。 */
function mapSsePayload(raw: string): AgentEvent | null {
  try {
    return JSON.parse(raw) as AgentEvent;
  } catch {
    return null;
  }
}

/** 逐行读 SSE 流（text/event-stream）。 */
async function* readSse(response: Response): AsyncGenerator<{ data: string }> {
  const body = response.body;
  if (!body) return;
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index = buffer.indexOf("\n\n");
    while (index >= 0) {
      const chunk = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const data = chunk
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("\n");
      if (data) yield { data };
      index = buffer.indexOf("\n\n");
    }
  }
}

export function startAgentRunWithEvents(
  request: LaunchAgentRunRequest,
  onEvent: (event: AgentEvent) => void,
): AgentRunHandle {
  const runId = request.runId ?? createRunId();
  const controller = new AbortController();
  let settled = false;

  const done = (async () => {
    const base = resolveBaseUrl();
    const url = `${base}${apiPaths.agentWorkRun(request.workId)}`;
    const body = { prompt: request.prompt, run_id: runId };

    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(text || `Agent 启动失败 HTTP ${response.status}`);
    }

    let exitCode = 0;
    for await (const { data } of readSse(response)) {
      const event = mapSsePayload(data);
      if (!event) continue;
      onEvent(event);
      // 让出一帧，避免同 tick 批处理把多段思考一次刷上屏（化开交给 UI CharReveal）
      if (event.type === "thinking" || event.type === "textDelta") {
        await new Promise<void>((resolve) => {
          window.requestAnimationFrame(() => resolve());
        });
      }
      if (event.type === "runCompleted") {
        exitCode = event.exitCode;
        settled = true;
        return { runId, exitCode };
      }
    }
    if (!settled) {
      onEvent({ type: "runCompleted", exitCode: 0 });
    }
    return { runId, exitCode };
  })();

  return {
    runId,
    done,
    cancel: async () => {
      controller.abort();
      if (!settled) {
        onEvent({ type: "runCompleted", exitCode: 1 });
      }
    },
  };
}
