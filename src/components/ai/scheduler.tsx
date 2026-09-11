/**
 * AI 工作区调度器：注册块、对接后端 SSE、编排左侧渲染。
 * 活回合：SSE 增量流式；历史 hydrate：一次铺开，不流式。
 */

import { memo, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { ComposerAgentOption, ComposerSubmitPayload } from "@/contracts/composer";
import type {
  AgentWorkDetailView,
  AgentWorkMessageView,
  AgentWorkProductItem,
  AgentWorkProductsView,
  AgentWorkStepView,
  AgentWorkTimelineEntry,
} from "@/contracts/ai-work";
import type { CrawlProductItem } from "@/contracts/crawler";
import {
  applyRunStateToDetail,
  createAgentRunMessageState,
  createOptimisticSendDetail,
  reduceAgentEvent,
} from "@/lib/agent-event-reducer";
import { startAgentRunWithEvents } from "@/lib/agent-run";
import { useDiscoveryStore } from "@/stores/discovery-store";
import { PromptComposer } from "@/components/composer";
import { useComposerAgentOptions } from "@/components/composer/composer-agents";
import { Card, CardContent } from "@/components/ui/card";
import { UserBlock, ThinkingBlock, TextBlock, StepBlock } from "./blocks";
import { ThinkingOrb } from "./ThinkingOrb";
import { nearBottom, nextFollowIntent, type FollowIntent, type ScrollSample } from "./stick-to-bottom";

export interface SendHandle {
  runId: string;
  promise: Promise<AgentWorkDetailView>;
  cancel: () => Promise<void>;
}

/** 调度后的块描述。 */
export type ScheduledBlock =
  | {
      kind: "user";
      id: string;
      messageId: string;
      content: string;
      attachments?: AgentWorkMessageView["attachments"];
    }
  | {
      kind: "thinking";
      id: string;
      text: string;
      streaming: boolean;
      startedAt?: string | null;
      durationSec?: number | null;
    }
  | {
      kind: "step";
      id: string;
      step: AgentWorkStepView;
      pageUrl: string | null;
      products: AgentWorkProductItem[];
    }
  | { kind: "text"; id: string; text: string; streaming: boolean };

const BLOCKS = {
  user: UserBlock,
  thinking: ThinkingBlock,
  step: StepBlock,
  text: TextBlock,
} as const;

function productsForStep(items: AgentWorkProductItem[], stepId: string): AgentWorkProductItem[] {
  return items.filter((item) => item.step_id === stepId);
}

function resolveStepPageUrl(detail: AgentWorkDetailView, step: AgentWorkStepView): string | null {
  if (!step.browser_frame_id) return null;
  if (detail.browser_live.frame_id === step.browser_frame_id) {
    const url = detail.browser_live.url;
    return url && url !== "about:blank" ? url : null;
  }
  return detail.browser_history.find((item) => item.id === step.browser_frame_id)?.url ?? null;
}

function scheduleFromTimeline(
  messageId: string,
  timeline: AgentWorkTimelineEntry[],
  steps: AgentWorkStepView[],
  detail: AgentWorkDetailView,
  streaming: boolean,
  meta: { startedAt?: string | null; durationSec?: number | null },
): ScheduledBlock[] {
  const lastIdx = timeline.length - 1;
  const out: ScheduledBlock[] = [];
  for (let i = 0; i < timeline.length; i++) {
    const entry = timeline[i];
    const isLast = i === lastIdx;
    // 只有时间线最末一段在 busy 时带光标；前面的段视为已输出完
    const live = streaming && isLast;
    if (entry.kind === "thinking") {
      out.push({
        kind: "thinking",
        id: `${messageId}-${entry.id}`,
        text: entry.text,
        streaming: live,
        startedAt: meta.startedAt,
        durationSec: isLast ? meta.durationSec : null,
      });
      continue;
    }
    if (entry.kind === "step") {
      const step = steps.find((item) => item.id === entry.id);
      if (!step) continue;
      out.push({
        kind: "step",
        id: `${messageId}-step-${step.id}`,
        step,
        pageUrl: resolveStepPageUrl(detail, step),
        products: productsForStep(detail.products.items, step.id),
      });
      continue;
    }
    out.push({
      kind: "text",
      id: `${messageId}-${entry.id}`,
      text: entry.text,
      streaming: live,
    });
  }
  return out;
}

function scheduleLegacy(
  message: AgentWorkMessageView,
  detail: AgentWorkDetailView,
  streaming: boolean,
): ScheduledBlock[] {
  const thinking = (message.thinking ?? "").trim();
  const steps = message.steps ?? [];
  const hasContent = Boolean(message.content?.trim());
  const out: ScheduledBlock[] = [];
  const startedAt = message.thinking_started_at ?? message.created_at;
  const durationSec = message.thinking_duration_sec ?? null;
  // 末段才 live：有正文则正文；否则有工具则无光标；否则思考
  const thinkingLive = streaming && !hasContent && steps.length === 0;
  const textLive = streaming && hasContent;

  if (thinking) {
    out.push({
      kind: "thinking",
      id: `${message.id}-thinking`,
      text: thinking,
      streaming: thinkingLive,
      startedAt,
      durationSec,
    });
  }

  for (const step of steps) {
    out.push({
      kind: "step",
      id: `${message.id}-step-${step.id}`,
      step,
      pageUrl: resolveStepPageUrl(detail, step),
      products: productsForStep(detail.products.items, step.id),
    });
  }

  if (hasContent) {
    out.push({
      kind: "text",
      id: `${message.id}-text`,
      text: message.content ?? "",
      streaming: textLive,
    });
  }

  return out;
}

/** 单轮会话：用户消息 + 其后助手块（用于 sticky 分区）。 */
export type ScheduledTurn = {
  id: string;
  user: Extract<ScheduledBlock, { kind: "user" }> | null;
  blocks: ScheduledBlock[];
};

/** 把一条消息排成有序块（用户 / 助手）。 */
export function scheduleMessage(
  message: AgentWorkMessageView,
  detail: AgentWorkDetailView,
  streaming: boolean,
): ScheduledBlock[] {
  if (message.role === "user") {
    return [
      {
        kind: "user",
        id: `user-${message.id}`,
        messageId: message.id,
        content: message.content,
        attachments: message.attachments,
      },
    ];
  }

  const timeline = message.timeline ?? [];
  if (timeline.length > 0) {
    return scheduleFromTimeline(message.id, timeline, message.steps ?? [], detail, streaming, {
      startedAt: message.thinking_started_at ?? message.created_at,
      durationSec: message.thinking_duration_sec ?? null,
    });
  }
  return scheduleLegacy(message, detail, streaming);
}

/** 整页对话：按「用户 + 随后助手」切成轮次，便于 sticky。 */
export function scheduleTurns(detail: AgentWorkDetailView, busy: boolean): ScheduledTurn[] {
  const lastAssistantId = [...detail.messages].reverse().find((m) => m.role === "assistant")?.id;
  const turns: ScheduledTurn[] = [];
  let current: ScheduledTurn | null = null;

  const pushOrphan = (blocks: ScheduledBlock[]) => {
    if (blocks.length === 0) return;
    turns.push({ id: `orphan-${turns.length}-${blocks[0]?.id ?? "x"}`, user: null, blocks });
  };

  for (const message of detail.messages) {
    const streaming = busy && message.id === lastAssistantId && message.role === "assistant";
    const scheduled = scheduleMessage(message, detail, streaming);
    if (message.role === "user") {
      const user = scheduled.find((block): block is Extract<ScheduledBlock, { kind: "user" }> =>
        block.kind === "user",
      );
      if (!user) continue;
      current = { id: `turn-${message.id}`, user, blocks: [] };
      turns.push(current);
      continue;
    }
    if (current) {
      current.blocks.push(...scheduled);
    } else {
      pushOrphan(scheduled);
    }
  }
  return turns;
}

/** @deprecated 兼容旧调用；优先用 scheduleTurns。 */
export function scheduleDetail(detail: AgentWorkDetailView, busy: boolean): ScheduledBlock[] {
  return scheduleTurns(detail, busy).flatMap((turn) =>
    turn.user ? [turn.user, ...turn.blocks] : turn.blocks,
  );
}

function renderAssistantBlock(
  block: Exclude<ScheduledBlock, { kind: "user" }>,
  opts: {
    selectedStepId: string | null;
    onSelectStep?: (step: AgentWorkStepView) => void;
  },
): ReactNode {
  switch (block.kind) {
    case "thinking":
      return (
        <BLOCKS.thinking
          key={block.id}
          text={block.text}
          streaming={block.streaming}
          startedAt={block.startedAt}
          durationSec={block.durationSec}
        />
      );
    case "step":
      return (
        <BLOCKS.step
          key={block.id}
          step={block.step}
          pageUrl={block.pageUrl}
          products={block.products}
          selected={opts.selectedStepId === block.step.id}
          onSelect={opts.onSelectStep}
        />
      );
    case "text":
      return <BLOCKS.text key={block.id} text={block.text} streaming={block.streaming} />;
    default:
      return null;
  }
}

function extractProducts(output: unknown): CrawlProductItem[] {
  if (!output || typeof output !== "object") return [];
  const record = output as Record<string, unknown>;
  if (typeof record.platform !== "string" || !record.platform) return [];
  const platform = record.platform as CrawlProductItem["platform"];
  const now = new Date().toISOString();

  const rows: unknown[] = Array.isArray(record.items)
    ? record.items
    : record.item && typeof record.item === "object"
      ? [record.item]
      : [];

  const out: CrawlProductItem[] = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const item = row as Record<string, unknown>;
    const id = String(item.item_id ?? item.id ?? "");
    const title = String(item.title ?? "").trim();
    if (!id || !title) continue;
    out.push({
      id,
      title,
      price: String(item.price ?? ""),
      platform,
      seller: typeof item.seller_nick === "string" ? item.seller_nick : undefined,
      location: typeof item.location === "string" ? item.location : undefined,
      image_url: typeof item.image_url === "string" ? item.image_url : undefined,
      product_url:
        typeof item.url === "string"
          ? item.url
          : typeof item.product_url === "string"
            ? item.product_url
            : undefined,
      want_count: typeof item.want_count === "string" ? item.want_count : undefined,
      browse_count: typeof item.browse_count === "string" ? item.browse_count : undefined,
      desc: typeof item.desc === "string" ? item.desc : undefined,
      comments: parseComments(item.comments),
      ocr_text: typeof item.ocr_text === "string" ? item.ocr_text : undefined,
      content_text: typeof item.content_text === "string" ? item.content_text : undefined,
      note_type: typeof item.note_type === "string" ? item.note_type : undefined,
      xsec_token: typeof item.xsec_token === "string" ? item.xsec_token : undefined,
      crawled_at: now,
    });
  }
  return out;
}

function parseComments(value: unknown): CrawlProductItem["comments"] {
  if (!Array.isArray(value)) return [];
  const out: NonNullable<CrawlProductItem["comments"]> = [];
  for (const row of value) {
    if (!row || typeof row !== "object") continue;
    const item = row as Record<string, unknown>;
    const content = String(item.content ?? "").trim();
    if (!content) continue;
    out.push({
      author: String(item.author ?? "").trim() || "匿名",
      content,
      time: typeof item.time === "string" ? item.time : null,
      reply: typeof item.reply === "string" ? item.reply : null,
    });
  }
  return out;
}

function mergeProducts(
  current: AgentWorkProductsView,
  items: CrawlProductItem[],
  stepId: string,
): AgentWorkProductsView {
  if (items.length === 0) return current;
  const byId = new Map<string, AgentWorkProductItem>(
    current.items.map((item) => [item.id, item]),
  );
  for (const item of items) {
    byId.set(item.id, { ...item, step_id: stepId });
  }
  const merged = [...byId.values()];
  return {
    ...current,
    items: merged,
    total: merged.length,
    status: {
      state: "ready",
      label: "已采集",
      hint: `共 ${merged.length} 条`,
      badge_class: "bg-emerald-500/15 text-emerald-600",
    },
  };
}

/** 跟后端打交道：外部 CLI SSE → 更新 detail。 */
export function send(
  detail: AgentWorkDetailView,
  payload: ComposerSubmitPayload,
  onUpdate: (next: AgentWorkDetailView) => void,
): SendHandle {
  const message = payload.message.trim();
  if (!message) {
    return {
      runId: "empty",
      promise: Promise.resolve(detail),
      cancel: async () => undefined,
    };
  }

  const runtimeId = (payload.agent_id || detail.composer_agent_id || "codex").trim();
  if (runtimeId === "dingda" || runtimeId === "product") {
    return {
      runId: "blocked",
      promise: Promise.reject(new Error("产品 Agent 尚未开放，请在设置里选择 Codex / Claude")),
      cancel: async () => undefined,
    };
  }

  const { detail: optimistic, assistantMessageId } = createOptimisticSendDetail(
    detail,
    message,
    runtimeId,
    payload.model_id,
  );
  let snapshot: AgentWorkDetailView = {
    ...optimistic,
    status: { ...optimistic.status, hint: `${runtimeId} 执行中…` },
  };
  onUpdate(snapshot);

  let runState = createAgentRunMessageState();
  const catalogCommand =
    useDiscoveryStore.getState().agents.find((agent) => agent.id === runtimeId)?.command?.trim() ||
    null;

  const resumeSession =
    snapshot.cli_session_id &&
    (snapshot.cli_session_runtime_id ?? snapshot.composer_agent_id) === runtimeId
      ? snapshot.cli_session_id
      : null;

  const handle = startAgentRunWithEvents(
    {
      runtimeId,
      prompt: message,
      modelId: payload.model_id,
      platformHint: payload.crawl_platform ?? null,
      executable: catalogCommand,
      sessionId: resumeSession,
    },
    (event) => {
      runState = reduceAgentEvent(runState, event);
      snapshot = applyRunStateToDetail(snapshot, assistantMessageId, runState);
      if (event.type === "toolResult") {
        const products = extractProducts(event.output);
        if (products.length > 0) {
          snapshot = {
            ...snapshot,
            products: mergeProducts(snapshot.products, products, event.id ?? ""),
          };
        }
      }
      onUpdate(snapshot);
    },
  );

  const promise = handle.done.then(() => {
    snapshot = {
      ...snapshot,
      can_send: true,
      status: {
        state: runState.error ? "error" : "ready",
        label: runState.error ? "执行失败" : "已完成",
        hint: runState.error ?? null,
        badge_class: runState.error
          ? "bg-red-500/15 text-red-700"
          : "bg-emerald-500/15 text-emerald-600",
      },
    };
    onUpdate(snapshot);
    return snapshot;
  });

  return { runId: handle.runId, promise, cancel: handle.cancel };
}

const ComposerFooter = memo(function ComposerFooter({
  agents,
  defaultAgentId,
  defaultModelId,
  placeholder,
  disabled,
  busy,
  onSend,
  onCancel,
  onInputActivity,
}: {
  agents: ComposerAgentOption[];
  defaultAgentId?: string | null;
  defaultModelId?: string | null;
  placeholder?: string | null;
  disabled: boolean;
  busy: boolean;
  onSend?: (payload: ComposerSubmitPayload) => void;
  onCancel?: () => void;
  onInputActivity?: () => void;
}) {
  return (
    <footer className="shrink-0 border-t border-border/70 p-3">
      <Card size="sm" className="gap-0 py-2 shadow-sm">
        <CardContent className="px-3 pb-2 pt-2">
          <PromptComposer
            agents={agents}
            defaultAgentId={defaultAgentId}
            defaultModelId={defaultModelId}
            hideAgentPicker
            placeholder={placeholder ?? "输入关键词，如：露营椅 / 咖啡"}
            disabled={disabled}
            busy={busy}
            minRows={3}
            textareaClassName="min-h-[72px] text-sm"
            onSubmit={(payload) => onSend?.(payload)}
            onCancel={onCancel}
            onInputActivity={onInputActivity}
          />
        </CardContent>
      </Card>
    </footer>
  );
});

export interface ChatPaneProps {
  detail: AgentWorkDetailView;
  busy?: boolean;
  error?: string | null;
  selectedStepId?: string | null;
  onSend?: (payload: ComposerSubmitPayload) => void;
  onCancel?: () => void;
  onSelectStep?: (step: AgentWorkStepView) => void;
  /** 编辑某条用户消息：截断后从此处重新生成。 */
  onResubmitUser?: (messageId: string, content: string) => void;
}

/** 等待 Agent：时间线最外层；正在打字的块不显示（对齐 Cursor）。 */
function WorkingIndicator() {
  return (
    <div
      className="flex items-center gap-2 py-1 text-[13px] text-muted-foreground"
      aria-live="polite"
      aria-label="Agent 工作中"
    >
      <ThinkingOrb />
      <span>工作中…</span>
    </div>
  );
}

/** 末块是否正在流式输出（有光标）。 */
function isActivelyStreaming(turn: ScheduledTurn | undefined): boolean {
  if (!turn || turn.blocks.length === 0) return false;
  const last = turn.blocks[turn.blocks.length - 1];
  return (last.kind === "thinking" || last.kind === "text") && last.streaming;
}

/**
 * 先思考后结论：尚未出正文时隐藏 text；工具/浏览器步骤始终保留。
 */
function blocksForPhase(blocks: ScheduledBlock[]): ScheduledBlock[] {
  let lastThinking = -1;
  let lastText = -1;
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];
    if (block.kind === "thinking") lastThinking = i;
    if (block.kind === "text") lastText = i;
  }
  if (lastThinking > lastText) {
    return blocks.filter((block) => block.kind !== "text");
  }
  return blocks;
}

type ChatRow =
  | { kind: "turn"; id: string; turn: ScheduledTurn; turnIndex: number }
  | { kind: "tail"; id: "tail" };

function readScrollSample(el: HTMLElement): ScrollSample {
  return {
    scrollTop: el.scrollTop,
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight,
  };
}

/** 左侧聊天：虚拟滚动 + 顶部粘性用户消息。 */
export function ChatPane({
  detail,
  busy = false,
  error = null,
  selectedStepId = null,
  onSend,
  onCancel,
  onSelectStep,
  onResubmitUser,
}: ChatPaneProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const followRef = useRef<FollowIntent>({ following: true, escaped: false });
  const lastSampleRef = useRef<ScrollSample | null>(null);
  const liveAgents = useComposerAgentOptions();
  const agents = detail.composer_agents.length > 0 ? detail.composer_agents : liveAgents;
  const turns = scheduleTurns(detail, busy);
  const lastTurn = turns[turns.length - 1];
  const lastPhaseBlocks = lastTurn ? blocksForPhase(lastTurn.blocks) : [];
  const showWorking =
    busy &&
    !isActivelyStreaming(
      lastTurn ? { ...lastTurn, blocks: lastPhaseBlocks } : undefined,
    );

  const rows = useMemo<ChatRow[]>(() => {
    const list: ChatRow[] = turns.map((turn, turnIndex) => ({
      kind: "turn",
      id: turn.id,
      turn,
      turnIndex,
    }));
    if (error || showWorking) list.push({ kind: "tail", id: "tail" });
    return list;
  }, [turns, error, showWorking]);

  const fingerprint =
    turns.length +
    turns.reduce((sum, turn) => {
      const userLen = turn.user?.content.length ?? 0;
      const bodyLen = turn.blocks.reduce((inner, block) => {
        if (block.kind === "thinking" || block.kind === "text") return inner + block.text.length;
        return inner + 1;
      }, 0);
      return sum + userLen + bodyLen;
    }, 0) +
    (showWorking ? 1 : 0) +
    (error ? 1 : 0);

  const [stickyIndex, setStickyIndex] = useState(0);
  const [stickyPinned, setStickyPinned] = useState(false);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) => (rows[index]?.kind === "tail" ? 48 : 320),
    overscan: 4,
    getItemKey: (index) => rows[index]?.id ?? index,
  });

  const syncStickyAndFollow = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const sample = readScrollSample(el);
    const prev = lastSampleRef.current ?? sample;
    const next = nextFollowIntent(followRef.current, prev, sample);
    followRef.current = next;
    lastSampleRef.current = sample;
    if (nearBottom(sample) && !next.escaped) {
      followRef.current = { following: true, escaped: false };
    }

    let active = 0;
    for (let i = 0; i < turns.length; i++) {
      const start = virtualizer.getOffsetForIndex(i, "start");
      if (start == null) continue;
      const top = start[0];
      if (top <= sample.scrollTop + 8) active = i;
    }
    setStickyIndex(active);

    const activeStart = virtualizer.getOffsetForIndex(active, "start");
    const pinned = activeStart != null && sample.scrollTop > activeStart[0] + 4;
    setStickyPinned(pinned);
  }, [turns.length, virtualizer]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    syncStickyAndFollow();
    el.addEventListener("scroll", syncStickyAndFollow, { passive: true });
    return () => el.removeEventListener("scroll", syncStickyAndFollow);
  }, [syncStickyAndFollow]);

  useEffect(() => {
    syncStickyAndFollow();
  }, [fingerprint, virtualizer.getTotalSize(), syncStickyAndFollow]);

  useEffect(() => {
    if (!followRef.current.following) return;
    if (rows.length === 0) return;
    const frame = window.requestAnimationFrame(() => {
      virtualizer.scrollToIndex(rows.length - 1, { align: "end" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [fingerprint, busy, rows.length, virtualizer]);

  const stickyTurn = turns[stickyIndex] ?? null;
  const stickyUser = stickyPinned ? stickyTurn?.user ?? null : null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-center border-b border-border/70 px-4 py-3">
        <p className="truncate font-mono text-xs text-muted-foreground">{detail.work_id}</p>
      </header>

      <div className="relative min-h-0 flex-1">
        {stickyUser ? (
          <div className="pointer-events-auto absolute top-0 right-0 left-0 z-20 border-b border-border/40 bg-card/95 px-4 py-2 backdrop-blur-sm supports-[backdrop-filter]:bg-card/80">
            <div className="mx-auto w-full max-w-3xl">
              <BLOCKS.user
                content={stickyUser.content}
                attachments={stickyUser.attachments}
                editable={!busy}
                onResubmit={
                  onResubmitUser
                    ? (content) => onResubmitUser(stickyUser.messageId, content)
                    : undefined
                }
              />
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
                      {showWorking ? <WorkingIndicator /> : null}
                    </div>
                  ) : (
                    <TurnSection
                      turn={item.turn}
                      turnIndex={item.turnIndex}
                      busy={busy}
                      selectedStepId={selectedStepId}
                      onSelectStep={onSelectStep}
                      onResubmitUser={onResubmitUser}
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
        onSend={onSend}
        onCancel={onCancel}
        onInputActivity={() => {
          if (!followRef.current.following) return;
          window.requestAnimationFrame(() => {
            virtualizer.scrollToIndex(Math.max(0, rows.length - 1), { align: "end" });
          });
        }}
      />
    </div>
  );
}

function TurnSection({
  turn,
  turnIndex,
  busy,
  selectedStepId,
  onSelectStep,
  onResubmitUser,
}: {
  turn: ScheduledTurn;
  turnIndex: number;
  busy: boolean;
  selectedStepId: string | null;
  onSelectStep?: (step: AgentWorkStepView) => void;
  onResubmitUser?: (messageId: string, content: string) => void;
}) {
  const phaseBlocks = blocksForPhase(turn.blocks);
  return (
    <section className="relative" data-turn-index={turnIndex}>
      {turn.user ? (
        <div className="py-2">
          <BLOCKS.user
            content={turn.user.content}
            attachments={turn.user.attachments}
            editable={!busy}
            onResubmit={
              onResubmitUser
                ? (content) => onResubmitUser(turn.user!.messageId, content)
                : undefined
            }
          />
        </div>
      ) : null}
      {phaseBlocks.length > 0 ? (
        <div className="space-y-4 py-3">
          {phaseBlocks.map((block) => {
            if (block.kind === "user") return null;
            return renderAssistantBlock(block, { selectedStepId, onSelectStep });
          })}
        </div>
      ) : (
        <div className="h-2" aria-hidden />
      )}
    </section>
  );
}
