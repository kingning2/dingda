/**
 * Agent 运行：统一走 Python Server SSE。
 *
 * 一次运行的生命周期归服务端（见 ``agent.runs``）：客户端断开只是退订，
 * 不会把 run 掐掉。所以这里有两条起手路径 —— 新开一轮（POST）与接回在跑的
 * 那一轮（GET 重放 + 续播），后者还兼作断线续传。
 *
 * SSE 帧里的 ``id:`` 行是服务端投递日志的 ``seq``：客户端记住它，掉线后从
 * 该游标续传（服务端只补 ``seq > after`` 的幸存的条目）。它也是将来接 AG-UI 时
 * ``Last-Event-ID`` 的载体。
 */

import type { AgentEvent } from "@v2/contracts/agent-event";
import { resolveBaseUrl } from "@v2/runtime/http-client";

/** 一次运行的入参；字段与后端 `/v1/agent/runtimes/{id}/run` 的 body 一一对应。 */
export interface LaunchAgentRunRequest {
  runtimeId: string;
  prompt: string;
  modelId?: string | null;
  runId?: string | null;
  /** 这次运行属于哪条工作对话；断线后客户端靠它找回在跑的那条 run */
  workId?: string | null;
  /** 本轮优先爬取平台 */
  platformHint?: string | null;
  /** 换 Agent 冷启动：叮答托管的先前对话 */
  contextMessages?: Array<{ role: string; content: string }> | null;
}

/** 生成一次运行的 id；前端先用它占位，后端按同一个 id 回报进度与取消。 */
export function createRunId(): string {
  return `run-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * 起手失败：带上 HTTP 状态。
 *
 * 调用方据状态决定要不要续传 —— 404 是「这条 run 已经不在了」（结束太久被回收），
 * 重试没有意义；其余（5xx / 连接被掐）都可以再来一次。
 */
export class AgentStreamError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "AgentStreamError";
  }
}

/** 一帧 SSE：`id:` 给服务端 seq（缺省 null，例如服务端没编号的旧帧）。 */
interface SseFrame {
  id: number | null;
  event: string;
  data: unknown;
}

function mapSsePayload(raw: unknown): AgentEvent | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  if (typeof record.type !== "string") return null;
  return record as unknown as AgentEvent;
}

async function* readSse(response: Response): AsyncGenerator<SseFrame> {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";
  let id: number | null = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      if (line.startsWith("id:")) {
        const seq = Number.parseInt(line.slice(3).trim(), 10);
        id = Number.isFinite(seq) ? seq : null;
        continue;
      }
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
        continue;
      }
      if (line.startsWith("data:")) {
        const text = line.slice(5).trim();
        let data: unknown = text;
        try {
          data = JSON.parse(text);
        } catch {
          /* 非 JSON 就按原文交给上层，由它决定认不认 */
        }
        yield { id, event: eventName, data };
        eventName = "message";
        id = null;
      }
    }
  }
}

/**
 * 读完一条 SSE 响应：逐帧回报，返回退出码。
 *
 * 流结束却没见到 `runCompleted`（例如服务端进程被杀）时补发一个，别让折叠
 * 永远收不了尾。正常路径下 ``agent.runs`` 保证收尾事件一定发出，走不到这里。
 */
async function consumeRunStream(
  response: Response,
  onEvent: (event: AgentEvent) => void,
  onSeq?: (seq: number) => void,
): Promise<number> {
  for await (const frame of readSse(response)) {
    if (frame.id !== null) onSeq?.(frame.id);
    const event = mapSsePayload(frame.data);
    if (!event) continue;
    onEvent(event);
    if (event.type === "runCompleted") return event.exitCode;
  }
  onEvent({ type: "runCompleted", exitCode: 0 });
  return 0;
}

/** 一次运行的句柄：拿 runId、等结束、主动取消。 */
export interface AgentRunHandle {
  runId: string;
  done: Promise<{ runId: string; exitCode: number }>;
  /** 不看这一轮了，但让它在服务端继续跑（离开页面时用）。 */
  detach: () => void;
  /** 叫停这一轮（用户点了停止）。 */
  cancel: () => Promise<void>;
}

async function raiseForStatus(response: Response, fallback: string): Promise<never> {
  const text = await response.text().catch(() => "");
  throw new AgentStreamError(text || `${fallback} HTTP ${response.status}`, response.status);
}

/** 主动取消服务端仍在跑的 run。 */
async function requestCancel(runId: string): Promise<void> {
  try {
    await fetch(
      `${resolveBaseUrl()}/v1/agent/runtimes/runs/${encodeURIComponent(runId)}/cancel`,
      { method: "POST" },
    );
  } catch {
    /* 取消失败不该再打扰用户：run 有服务端 TTL 兜底 */
  }
}

/** 跑一轮 Agent → Python `/v1/agent/runtimes/{id}/run` SSE。 */
export function startAgentRunWithEvents(
  request: LaunchAgentRunRequest,
  onEvent: (event: AgentEvent) => void,
  onSeq?: (seq: number) => void,
): AgentRunHandle {
  const runId = request.runId ?? createRunId();
  const controller = new AbortController();

  const done = (async () => {
    const base = resolveBaseUrl();
    const url = `${base}/v1/agent/runtimes/${encodeURIComponent(request.runtimeId)}/run`;
    const body = {
      prompt: request.prompt,
      model_id: request.modelId ?? null,
      run_id: runId,
      work_id: request.workId ?? null,
      platform_hint: request.platformHint ?? null,
      context_messages: request.contextMessages ?? null,
    };

    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) await raiseForStatus(response, "Agent 启动失败");

    return { runId, exitCode: await consumeRunStream(response, onEvent, onSeq) };
  })();

  const detach = () => {
    controller.abort();
  };
  const cancel = async () => {
    controller.abort();
    await requestCancel(runId);
  };

  return { runId, done, detach, cancel };
}

/**
 * 接回一次仍在服务端跑的运行：先重放 `seq > after` 的条目，再续播到 run 结束。
 *
 * `after=0` 是从头重放（刚进页面时的冷接回）；填已折叠到的 seq 就是断线续传。
 */
export function resumeAgentRun(
  runId: string,
  after: number,
  onEvent: (event: AgentEvent) => void,
  onSeq?: (seq: number) => void,
): AgentRunHandle {
  const controller = new AbortController();

  const done = (async () => {
    const base = resolveBaseUrl();
    const url = `${base}/v1/agent/runtimes/runs/${encodeURIComponent(runId)}/events?after=${after}`;
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "text/event-stream" },
      signal: controller.signal,
    });
    if (!response.ok) await raiseForStatus(response, "接回执行失败");

    return { runId, exitCode: await consumeRunStream(response, onEvent, onSeq) };
  })();

  const detach = () => {
    controller.abort();
  };
  const cancel = async () => {
    controller.abort();
    await requestCancel(runId);
  };

  return { runId, done, detach, cancel };
}
