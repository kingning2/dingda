/**
 * 左侧聊天面板。
 *
 * 职责：
 *   渲染一条聊天记录（记录本体 + 活动状态行 + 输入框），是「一个聊天记录」的完整表达。
 *
 * 设计说明：
 *   - 块通过注册表解析（见 chat-block.tsx），本组件不认识任何具体块 ——
 *     加一个块类型不需要改本文件。
 *   - 轮次计算在 schedule.ts（纯函数，可单测），滚动行为在 use-sticky-and-follow.ts，
 *     状态行在 working-status.tsx。本文件只负责把它们装到一起。
 *   - 虚拟滚动的单位是**轮次**而不是块：一轮的高度差异大，按轮切更稳。
 *   - `data-index` 必须保留：react-virtual 的 measureElement 靠它把 DOM 节点映射回下标。
 */

import { useEffect, useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { ComposerAgentOption, ComposerSubmitPayload } from "@v2/contracts/composer";
import type { AgentWorkDetailView, AgentWorkStepView } from "@v2/contracts/ai-work";
import { AGENT_RUN_PHASE_MAP, type AgentRunPhase } from "@v2/ui-agent/agent-run-phase";
import { ComposerFooter } from "../composer-footer";
import { ChatBlock } from "./chat-block";
import { ChatTurn } from "./chat-turn";
import { blocksForPhase, scheduleTurns } from "./schedule";
import { useStickyAndFollow } from "./use-sticky-and-follow";
import {
  WorkingIndicator,
  isActivelyStreaming,
  resolveWorkingDetails,
  shouldShowWorking,
} from "./working-status";
import type { ChatRenderContext, ChatTurn as ChatTurnData } from "./types";

/** 一轮的估算高度；真实高度由 measureElement 测出来后覆盖。 */
const TURN_ESTIMATED_HEIGHT = 320;
/** 错误尾行的估算高度。 */
const TAIL_ESTIMATED_HEIGHT = 48;

export interface ChatProps {
  detail: AgentWorkDetailView;
  /** 可选的 Agent 列表，由上层提供（layout 已算好，避免重复取一次）。 */
  agents: ComposerAgentOption[];
  busy?: boolean;
  /** 当前会话的前端运行阶段；历史回放时为 null。 */
  runPhase?: AgentRunPhase | null;
  error?: string | null;
  selectedStepId?: string | null;
  onSend?: (payload: ComposerSubmitPayload) => void;
  onCancel?: () => void;
  onSelectStep?: (step: AgentWorkStepView) => void;
  /** 编辑某条用户消息：截断后从此处重新生成。 */
  onResubmitUser?: (messageId: string, content: string) => void;
}

type ChatRow =
  | { kind: "turn"; id: string; turn: ChatTurnData; turnIndex: number }
  | { kind: "tail"; id: "tail" };

export function Chat({
  detail,
  agents,
  busy = false,
  runPhase = null,
  error = null,
  selectedStepId = null,
  onSend,
  onCancel,
  onSelectStep,
  onResubmitUser,
}: ChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  // 历史回放时 busy 为 false，阶段一律按 null 处理，避免残留的旧阶段影响渲染。
  const activePhase = busy ? runPhase : null;

  const turns = useMemo(
    () => scheduleTurns(detail, busy, activePhase),
    [detail, busy, activePhase],
  );

  const rows = useMemo<ChatRow[]>(() => {
    const list: ChatRow[] = turns.map((turn, turnIndex) => ({
      kind: "turn",
      id: turn.id,
      turn,
      turnIndex,
    }));
    if (error) list.push({ kind: "tail", id: "tail" });
    return list;
  }, [turns, error]);

  // 内容指纹：轮次数 + 各轮文字长度。用它代替深度比较，避免每帧重算 sticky。
  const fingerprint = useMemo(
    () =>
      turns.length +
      turns.reduce((sum, turn) => {
        const userLen = turn.user?.content.length ?? 0;
        const bodyLen = turn.blocks.reduce((inner, block) => {
          if (block.kind === "thinking" || block.kind === "text") return inner + block.text.length;
          return inner + 1;
        }, 0);
        return sum + userLen + bodyLen;
      }, 0) +
      (error ? 1 : 0),
    [turns, error],
  );

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) =>
      rows[index]?.kind === "tail" ? TAIL_ESTIMATED_HEIGHT : TURN_ESTIMATED_HEIGHT,
    overscan: 4,
    getItemKey: (index) => rows[index]?.id ?? index,
  });

  const { stickyIndex, stickyPinned, keepFollowingToEnd } = useStickyAndFollow({
    scrollRef,
    virtualizer,
    turns,
    fingerprint,
    busy,
    rowCount: rows.length,
  });

  useEffect(() => {
    if (!busy || !onCancel) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      onCancel();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [busy, onCancel]);

  const context: ChatRenderContext = {
    busy,
    selectedStepId,
    onSelectStep,
    onResubmitUser,
  };

  const lastTurn = turns[turns.length - 1];
  // 状态行看的是**未裁剪**的块：思考阶段被裁掉的正文，正是要显示成 `└` 详情的那一行。
  const lastPhaseBlocks = lastTurn ? blocksForPhase(lastTurn.blocks, activePhase) : [];
  const activePhaseView = activePhase ? AGENT_RUN_PHASE_MAP[activePhase] : null;
  const showWorking = busy && shouldShowWorking(activePhase, isActivelyStreaming(lastPhaseBlocks));
  const workingDetails = resolveWorkingDetails(
    lastTurn?.blocks ?? [],
    activePhase,
    activePhaseView?.hint ?? null,
  );
  const activeAssistant = [...detail.messages].reverse().find((m) => m.role === "assistant");

  const stickyTurn = turns[stickyIndex] ?? null;
  const stickyUser = stickyPinned ? (stickyTurn?.user ?? null) : null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="relative min-h-0 flex-1">
        {stickyUser ? (
          <div className="pointer-events-auto absolute top-0 right-0 left-0 z-20 border-b border-border/40 bg-card/95 px-4 py-2 backdrop-blur-sm supports-[backdrop-filter]:bg-card/80">
            <div className="mx-auto w-full max-w-3xl">
              <ChatBlock block={stickyUser} context={context} />
            </div>
          </div>
        ) : null}

        <div ref={scrollRef} className="h-full overflow-y-auto px-4 py-5">
          <div
            className="relative mx-auto w-full max-w-3xl"
            style={{ height: `${virtualizer.getTotalSize()}px` }}
          >
            {virtualizer.getVirtualItems().map((row) => {
              const item = rows[row.index];
              if (!item) return null;
              return (
                <div
                  key={item.id}
                  data-index={row.index}
                  ref={virtualizer.measureElement}
                  className="absolute top-0 left-0 w-full"
                  style={{ transform: `translateY(${row.start}px)` }}
                >
                  {item.kind === "tail" ? (
                    <div className="space-y-2 py-2">
                      {error ? <p className="text-sm text-destructive">{error}</p> : null}
                    </div>
                  ) : (
                    <ChatTurn
                      turn={item.turn}
                      index={item.turnIndex}
                      // 阶段只对最末一轮有效：历史轮次永远静态铺开。
                      runPhase={item.turnIndex === turns.length - 1 ? activePhase : null}
                      context={context}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <ComposerFooter
        agents={agents}
        defaultAgentId={detail.composer_agent_id}
        defaultModelId={detail.composer_model_id}
        placeholder={detail.composer_placeholder}
        disabled={!detail.can_send && !busy}
        busy={busy}
        status={
          showWorking ? (
            <WorkingIndicator
              label={activePhaseView?.workingLabel ?? "Working"}
              details={workingDetails}
              startedAt={activeAssistant?.thinking_started_at ?? activeAssistant?.created_at}
            />
          ) : null
        }
        onSend={onSend}
        onCancel={onCancel}
        onInputActivity={keepFollowingToEnd}
      />
    </div>
  );
}
