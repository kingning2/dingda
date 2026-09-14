/**
 * Agent 运行：统一走 Python Server SSE（当前仅外部 CLI）。
 */

import type { AgentEvent } from "@v2/contracts/agent-event";
import { resolveBaseUrl } from "@v2/runtime/http-client";

/** 一次运行的入参；字段与后端 `/v1/agent/runtimes/{id}/run` 的 body 一一对应。 */
export interface LaunchAgentRunRequest {
  runtimeId: string;
  prompt: string;
  cwd?: string | null;
  modelId?: string | null;
  sessionId?: string | null;
  reasoning?: string | null;
  /** Tauri 扫描到的 CLI 绝对路径 */
  executable?: string | null;
  extraAllowedDirs?: string[] | null;
  runId?: string | null;
  /** 本轮优先爬取平台 */
  platformHint?: string | null;
  /** 换 Agent 冷启动：叮答托管的先前对话 */
  contextMessages?: Array<{ role: string; content: string }> | null;
  /** 预留：产品 Agent work_id（当前未开放） */
  workId?: string | null;
}

/** 生成一次运行的 id；前端先用它占位，后端按同一个 id 回报进度与取消。 */
export function createRunId(): string {
  return `run-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function mapSsePayload(raw: unknown): AgentEvent | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  if (typeof record.type !== "string") return null;
  return record as unknown as AgentEvent;
}

async function* readSse(
  response: Response,
): AsyncGenerator<{ event: string; data: unknown }> {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
        continue;
      }
      if (line.startsWith("data:")) {
        const text = line.slice(5).trim();
        try {
          yield { event: eventName, data: JSON.parse(text) };
        } catch {
          yield { event: eventName, data: text };
        }
        eventName = "message";
      }
    }
  }
}

/** 一次运行的句柄：拿 runId、等结束、主动取消。 */
export interface AgentRunHandle {
  runId: string;
  done: Promise<{ runId: string; exitCode: number }>;
  cancel: () => Promise<void>;
}

const PRODUCT_RUNTIME_IDS = new Set(["dingda", "product"]);

function isProductRuntime(runtimeId: string): boolean {
  return PRODUCT_RUNTIME_IDS.has(runtimeId.trim().toLowerCase());
}

/** 外部 CLI → Python `/v1/agent/runtimes/{id}/run` SSE。 */
export function startAgentRunWithEvents(
  request: LaunchAgentRunRequest,
  onEvent: (event: AgentEvent) => void,
): AgentRunHandle {
  const runId = request.runId ?? createRunId();
  const controller = new AbortController();
  let settled = false;

  const done = (async () => {
    const base = resolveBaseUrl();
    const isProduct = isProductRuntime(request.runtimeId);
    if (isProduct) {
      throw new Error("产品 Agent 尚未开放，请选择 Codex / Claude / OpenCode 等外部 Agent");
    }
    const url = `${base}/v1/agent/runtimes/${encodeURIComponent(request.runtimeId)}/run`;
    const body = {
      prompt: request.prompt,
      cwd: request.cwd ?? null,
      model_id: request.modelId ?? null,
      session_id: request.sessionId ?? null,
      reasoning: request.reasoning ?? null,
      executable: request.executable ?? null,
      extra_allowed_dirs: request.extraAllowedDirs ?? null,
      run_id: runId,
      platform_hint: request.platformHint ?? null,
      context_messages: request.contextMessages ?? null,
    };

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
      try {
        await fetch(`${resolveBaseUrl()}/v1/agent/runtimes/runs/${encodeURIComponent(runId)}/cancel`, {
          method: "POST",
        });
      } catch {
        /* ignore */
      }
    },
  };
}
