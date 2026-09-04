import { useEffect, useState } from "react";
import type { AgentWorkMessageView, AgentWorkProductItem, AgentWorkStepView } from "@/contracts/ai-work";
import { Card, CardContent } from "@/components/ui/card";
import { MarkdownRenderer } from "../markdown";
import { TypewriterCursor, TypewriterMarkdown } from "./typewriter";
import { ThinkingBlock } from "../thinking/ThinkingBlock";
import { ToolCallCard } from "../tool/ToolCallCard";
import { cn } from "@/lib/utils";

interface AIMessageProps {
  message: AgentWorkMessageView;
  busy?: boolean;
  typewriterActive?: boolean;
  /** 由 mock/后端逐字推送正文时为 true，直接渲染 content。 */
  streaming?: boolean;
  onTypewriterComplete?: () => void;
  selectedStepId?: string | null;
  products?: AgentWorkProductItem[];
  resolveStepPageUrl?: (step: AgentWorkStepView) => string | null;
  productsForStep?: (stepId: string) => AgentWorkProductItem[];
  onSelectStep?: (step: AgentWorkStepView) => void;
  thinking?: string | null;
  className?: string;
}

function formatDuration(sec: number): string {
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}分${s}s`;
}

function elapsedSeconds(startedAt: string | null | undefined): number {
  if (!startedAt) return 0;
  const start = Date.parse(startedAt);
  if (Number.isNaN(start)) return 0;
  return Math.max(0, Math.floor((Date.now() - start) / 1000));
}

/** 无思考正文时的轻量计时/等待文案（不出现折叠块）。 */
function StatusLine({
  busy,
  startedAt,
  durationSec,
}: {
  busy: boolean;
  startedAt: string | null | undefined;
  durationSec: number | null;
}) {
  const [liveSec, setLiveSec] = useState(() => elapsedSeconds(startedAt));

  useEffect(() => {
    if (!busy || !startedAt) {
      setLiveSec(elapsedSeconds(startedAt));
      return;
    }
    setLiveSec(elapsedSeconds(startedAt));
    const timer = window.setInterval(() => {
      setLiveSec(elapsedSeconds(startedAt));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [busy, startedAt]);

  const sec = busy ? liveSec : (durationSec ?? liveSec);
  if (busy) {
    return (
      <p className="text-xs text-muted-foreground">
        正在处理{sec > 0 ? ` · ${formatDuration(sec)}` : "…"}
      </p>
    );
  }
  if (sec > 0) {
    return <p className="text-xs text-muted-foreground">用时 {formatDuration(sec)}</p>;
  }
  return null;
}

export function AIMessage({
  message,
  busy = false,
  typewriterActive = false,
  streaming = false,
  onTypewriterComplete,
  selectedStepId = null,
  resolveStepPageUrl,
  productsForStep,
  onSelectStep,
  thinking,
  className,
}: AIMessageProps) {
  const thinkingText = thinking?.trim() || "";
  const hasSteps = Boolean(message.steps && message.steps.length > 0);
  const hasContent = Boolean(message.content?.trim());
  const startedAt = message.thinking_started_at ?? message.created_at;
  const durationSec = message.thinking_duration_sec ?? null;
  // 只有真实思考正文才用折叠块；否则纯文字 + 秒数
  const showThinkingBlock = Boolean(thinkingText);
  const showStatusLine = !showThinkingBlock && (busy || durationSec != null);

  return (
    <Card
      size="sm"
      className={cn(
        "min-w-0 max-w-[92%] gap-2 overflow-hidden bg-muted/40 py-2.5 ring-border/80",
        className,
      )}
    >
      <CardContent className="min-w-0 space-y-2 break-words text-sm leading-relaxed">
        {showThinkingBlock ? (
          <ThinkingBlock
            content={thinkingText}
            busy={busy}
            startedAt={startedAt}
            durationSec={durationSec}
            defaultOpen
          />
        ) : null}

        {showStatusLine ? (
          <StatusLine busy={busy} startedAt={startedAt} durationSec={durationSec} />
        ) : null}

        {hasSteps ? (
          <div
            className={cn(
              "space-y-2",
              (showThinkingBlock || showStatusLine || hasContent || streaming) &&
                "border-t border-border/60 pt-2",
            )}
          >
            {message.steps!.map((step) => (
              <ToolCallCard
                key={step.id}
                step={step}
                selected={selectedStepId === step.id}
                pageUrl={resolveStepPageUrl?.(step) ?? null}
                products={productsForStep?.(step.id) ?? []}
                onSelect={onSelectStep}
              />
            ))}
          </div>
        ) : null}

        {hasContent || streaming ? (
          streaming ? (
            <div
              className={cn(
                "text-sm leading-relaxed",
                (hasSteps || showThinkingBlock || showStatusLine) && "border-t border-border/60 pt-2",
              )}
            >
              {hasContent ? <MarkdownRenderer content={message.content} /> : null}
              {busy ? <TypewriterCursor /> : null}
            </div>
          ) : (
            <div
              className={cn(
                (hasSteps || showThinkingBlock || showStatusLine) && "border-t border-border/60 pt-2",
              )}
            >
              <TypewriterMarkdown
                text={message.content}
                active={typewriterActive}
                busy={busy}
                onComplete={onTypewriterComplete}
                render={(visibleText) => <MarkdownRenderer content={visibleText} />}
              />
            </div>
          )
        ) : null}
      </CardContent>
    </Card>
  );
}
