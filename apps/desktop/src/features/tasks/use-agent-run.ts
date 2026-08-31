/**
 * 任务详情：水合 AgentRun + 订阅 progress + 暂停/继续/取消。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  agentRunCancel,
  agentRunGet,
  agentRunPause,
  agentRunResume,
  type AgentRunRecord,
  type AgentRunStep,
} from "@desk/platform/ipc/agent-run";
import { stringifyError } from "@desk/platform/error";
import {
  listenAgentProgress,
  type AgentProgressPayload,
} from "@desk/platform/events/agent";
import {
  buildAgentThoughts,
  formatStepLogText,
  parseCrawlContent,
  thoughtLabelForNode,
  upsertRunStep,
} from "./price-compare";

export type RunLogLine = {
  id: string;
  text: string;
  streaming?: boolean;
};

function seedLog(run: AgentRunRecord): RunLogLine[] {
  const lines: RunLogLine[] = [{ id: `${run.id}:user`, text: `查询：${run.user}` }];
  for (const step of [...run.steps].sort((a, b) => a.index - b.index)) {
    const line = formatStepLogLine(run.id, step);
    if (line) {
      lines.push(line);
    }
  }
  if (run.reply) {
    lines.push({ id: `${run.id}:reply`, text: run.reply });
  }
  if (run.error) {
    lines.push({ id: `${run.id}:error`, text: `错误：${run.error}` });
  }
  return lines;
}

function formatStepLogLine(runId: string, step: AgentRunStep): RunLogLine | null {
  if (step.node === "normalize" || step.node === "match" || step.node === "finalize") {
    return null;
  }
  const label = thoughtLabelForNode(step.node);
  const body = formatStepLogText(step.node, step.content ?? step.detail);
  const text = body ? `${label}\n${body}` : label;
  return {
    id: `${runId}:${step.node}:${step.index}`,
    text,
    streaming: step.status === "running",
  };
}

const TERMINAL_PROGRESS = new Set([
  "done",
  "error",
  "completed",
  "failed",
  "cancelled",
  "waiting_network",
  "paused",
]);

async function agentRunGetWithRetry(runId: string): Promise<AgentRunRecord> {
  const maxAttempts = 20;
  const delayMs = 150;
  let lastError: unknown;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      return await agentRunGet(runId);
    } catch (error) {
      lastError = error;
      const message = stringifyError(error);
      if (!message.includes("不存在") || attempt === maxAttempts - 1) {
        throw error;
      }
      await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    }
  }
  throw lastError;
}

function appendLog(prev: RunLogLine[], payload: AgentProgressPayload): RunLogLine[] {
  const streamId = `${payload.runId}:${payload.node ?? payload.index ?? "run"}:stream`;

  if (payload.status === "running") {
    const node = payload.node ?? "run";
    if (node === "normalize" || node === "match" || node === "finalize") {
      return prev;
    }
    const label = thoughtLabelForNode(node);
    const body = payload.content?.trim();
    const line: RunLogLine = {
      id: streamId,
      text: body ? `${label}\n${payload.content}` : label,
      streaming: true,
    };
    const idx = prev.findIndex((item) => item.id === streamId);
    if (idx >= 0) {
      const next = [...prev];
      next[idx] = line;
      return next;
    }
    return [...prev, line];
  }

  if (!TERMINAL_PROGRESS.has(payload.status)) {
    return prev;
  }

  const node = payload.node ?? "run";
  if (node === "normalize" || node === "match") {
    return prev;
  }
  const label = thoughtLabelForNode(node);
  let text = label;

  if (payload.status === "completed" && payload.content) {
    text = `${label}\n${payload.content}`;
  } else if (payload.status === "failed") {
    text = payload.detail ? `${label} — ${payload.detail}` : label;
  } else if (payload.node && payload.content) {
    const body = formatStepLogText(payload.node, payload.content);
    if (body) {
      text = `${label}\n${body}`;
    }
  } else if (payload.detail) {
    text = `${label} — ${payload.detail}`;
  }

  const done: RunLogLine = { id: streamId, text, streaming: false };
  const idx = prev.findIndex((item) => item.id === streamId);
  if (idx >= 0) {
    const next = [...prev];
    next[idx] = done;
    return next;
  }
  if (prev.some((line) => line.id === `${payload.runId}:${payload.stepId ?? payload.index ?? node}:${payload.status}`)) {
    return prev;
  }
  return [...prev, done];
}

export function useAgentRun(runId: string | undefined) {
  const [record, setRecord] = useState<AgentRunRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(runId));
  const [busy, setBusy] = useState(false);
  const [logLines, setLogLines] = useState<RunLogLine[]>([]);

  useEffect(() => {
    if (!runId) {
      setRecord(null);
      setError("缺少任务 ID");
      setLoading(false);
      setLogLines([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    void agentRunGetWithRetry(runId)
      .then((run) => {
        if (cancelled) {
          return;
        }
        setRecord(run);
        setLogLines(seedLog(run));
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setRecord(null);
        setError(err instanceof Error ? err.message : String(err));
        setLogLines([]);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  useEffect(() => {
    if (!runId) {
      return;
    }

    let unlisten: (() => void) | undefined;
    let disposed = false;

    void listenAgentProgress((payload) => {
      if (payload.runId !== runId) {
        return;
      }
      setRecord((prev) => {
        if (!prev) {
          return prev;
        }
        return upsertRunStep(prev, {
          node: payload.node,
          index: payload.index,
          status: payload.status,
          detail: payload.detail,
          content: payload.content,
          message: payload.message,
          errorKind: payload.errorKind,
          model: payload.model,
        });
      });
      setLogLines((prev) => appendLog(prev, payload));
    }).then((fn) => {
      if (disposed) {
        fn();
        return;
      }
      unlisten = fn;
    });

    return () => {
      disposed = true;
      unlisten?.();
    };
  }, [runId]);

  const runControl = useCallback(
    async (action: "pause" | "resume" | "cancel" | "restart" | "seek", node?: string) => {
      if (!runId || busy) {
        return;
      }
      setBusy(true);
      setError(null);
      try {
        const next =
          action === "pause"
            ? await agentRunPause(runId)
            : action === "resume"
              ? await agentRunResume({ runId, mode: "continue" })
              : action === "restart"
                ? await agentRunResume({ runId, mode: "restart" })
                : action === "seek"
                  ? await agentRunResume({ runId, mode: "seek", node })
                  : await agentRunCancel(runId);
        setRecord(next);
        setLogLines(seedLog(next));
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [busy, runId],
  );

  const thoughts = useMemo(() => buildAgentThoughts(record), [record]);

  const progressPercent = useMemo(() => {
    if (!record) {
      return 0;
    }
    if (record.state === "completed") {
      return 100;
    }
    const visible = thoughts.filter((item) => item.status !== "error");
    if (visible.length === 0) {
      return record.state === "running" ? 8 : 0;
    }
    const done = visible.filter((item) => item.status === "done").length;
    const running = visible.some((item) => item.status === "running");
    const base = (done / visible.length) * 100;
    return Math.round(running ? Math.min(96, base + 12) : base);
  }, [record, thoughts]);

  const crawlCounts = useMemo(() => {
    const crawl = record?.steps.find((step) => step.node === "crawl");
    const parsed = parseCrawlContent(crawl?.content);
    if (!parsed || parsed.items.length === 0) {
      return undefined;
    }
    const match = record?.steps.find((step) => step.node === "match");
    const matchedMatch = /(\d+)/.exec(match?.content ?? "");
    return {
      crawled: parsed.items.length,
      matched: matchedMatch ? Number(matchedMatch[1]) : undefined,
      failed: 0,
    };
  }, [record]);

  const statusMessage = useMemo(() => {
    if (!record) {
      return undefined;
    }
    if (record.state === "failed") {
      return record.error || "失败";
    }
    if (record.state === "completed") {
      return "已完成";
    }
    if (record.state === "cancelled") {
      return "已取消";
    }
    if (record.state === "paused") {
      return "已暂停";
    }
    if (record.state === "waiting_network") {
      return "等待网络恢复";
    }
    const running = record.steps.find((step) => step.status === "running");
    if (running) {
      return thoughtLabelForNode(running.node);
    }
    return stateMessage(record.state);
  }, [record]);

  const isActive =
    record?.state === "running" ||
    record?.state === "paused" ||
    record?.state === "waiting_network" ||
    record?.state === "created";

  return {
    record,
    error,
    loading,
    busy,
    logLines,
    thoughts,
    progressPercent,
    crawlCounts,
    statusMessage,
    isActive,
    pause: () => void runControl("pause"),
    resume: () => void runControl("resume"),
    cancel: () => void runControl("cancel"),
    restart: () => void runControl("restart"),
  };
}

function stateMessage(state: string): string {
  switch (state) {
    case "running":
      return "运行中";
    case "created":
      return "排队中";
    default:
      return state;
  }
}
