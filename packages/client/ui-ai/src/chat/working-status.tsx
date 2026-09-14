/**
 * Codex 风格的活动状态行。
 *
 * 职责：
 *   渲染「正在思考 / 执行 / 浏览」的状态行（含耗时与 esc 提示），并推导它下方的 `└` 详情。
 *
 * 设计说明：
 *   - 活动反馈由这里承担，而不是思考块：`blocks/thinking.tsx` 在 streaming 时返回 null，
 *     推理正文只在结束后作为可展开摘要留下。两处分工是为了不让同一信息出现两次。
 *   - 详情取自**当前阶段对应的最后一个块**：思考阶段取思考文本最后一行，
 *     执行 / 直播 / 商品阶段取步骤的 `label · hint`。
 *   - 只有阶段没有具体块可依据时，回落到阶段映射表里的 hint。
 */

import { useEffect, useState } from "react";
import { AGENT_RUN_PHASE_MAP, type AgentRunPhase } from "@v2/ui-agent/run/phase";
import { CodexActivityIndicator } from "../ThinkingOrb";
import type { ChatBlock } from "./types";

/** 把秒数格式化成 Codex TUI 的紧凑形式。 */
function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

/** Codex TUI 风格活动行：• Header (0s • esc to interrupt)，详情使用 └。 */
export function WorkingIndicator({
  label,
  details,
  startedAt,
}: {
  label: string;
  details?: string | null;
  startedAt?: string | null;
}) {
  const startMs = startedAt ? Date.parse(startedAt) : Number.NaN;
  const [elapsed, setElapsed] = useState(() =>
    Number.isNaN(startMs) ? 0 : Math.max(0, Math.floor((Date.now() - startMs) / 1000)),
  );

  useEffect(() => {
    if (Number.isNaN(startMs)) return;
    setElapsed(Math.max(0, Math.floor((Date.now() - startMs) / 1000)));
    const timer = window.setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - startMs) / 1000)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [startMs]);

  return (
    <div
      className="px-1 py-1.5 text-[13px] leading-relaxed text-muted-foreground"
      aria-live="polite"
      aria-label="Agent working"
    >
      <div className="flex min-w-0 items-center gap-2">
        <CodexActivityIndicator className="shrink-0 text-[14px]" />
        <span className="codex-status-shimmer shrink-0 font-medium text-foreground">
          {label}
        </span>
        <span className="truncate text-muted-foreground/80">
          ({formatElapsed(elapsed)} • esc to interrupt)
        </span>
      </div>
      {details ? (
        <p className="truncate pl-5 text-[12px] text-muted-foreground/80">
          {"└ "}
          {details}
        </p>
      ) : null}
    </div>
  );
}

/**
 * 末块是否正在流式输出。
 *
 * 入参必须是**已按阶段裁剪**的块：思考阶段被裁掉的正文不该被当成活跃块。
 */
export function isActivelyStreaming(blocks: ChatBlock[]): boolean {
  const last = blocks[blocks.length - 1];
  if (!last) return false;
  return (last.kind === "thinking" || last.kind === "text") && last.streaming;
}

/**
 * 状态行下方的 `└` 详情。
 *
 * 传**未裁剪**的块：思考阶段被裁掉的正文，恰恰是要展示成详情的那一行。
 */
export function resolveWorkingDetails(
  blocks: ChatBlock[],
  phase: AgentRunPhase | null,
  fallback: string | null,
): string | null {
  if (!phase) return fallback;

  if (phase === "thinking") {
    const thinking = [...blocks]
      .reverse()
      .find((block): block is Extract<ChatBlock, { kind: "thinking" }> => block.kind === "thinking");
    const lines = (thinking?.text ?? "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    return lines.length > 0 ? lines[lines.length - 1] : fallback;
  }

  if (phase === "executing" || phase === "live" || phase === "products") {
    const step = [...blocks]
      .reverse()
      .find((block): block is Extract<ChatBlock, { kind: "step" }> => block.kind === "step");
    if (step) return step.step.hint ? `${step.step.label} · ${step.step.hint}` : step.step.label;
  }

  return fallback;
}

/** 阶段是否该显示状态行。`outputting` 阶段有正文在流时由正文块承担反馈。 */
export function shouldShowWorking(
  phase: AgentRunPhase | null,
  activelyStreaming: boolean,
): boolean {
  if (!phase) return false;
  const view = AGENT_RUN_PHASE_MAP[phase];
  if (!view.workingLabel) return false;
  return !(phase === "outputting" && activelyStreaming);
}
