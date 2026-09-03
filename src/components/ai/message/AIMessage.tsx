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
  return (
    <Card
      size="sm"
      className={cn("max-w-[92%] gap-2 overflow-visible bg-muted/40 py-2.5 ring-border/80", className)}
    >
      <CardContent className="space-y-2 text-sm leading-relaxed">
        {thinking || (busy && streaming) ? (
          <ThinkingBlock content={thinking ?? ""} busy={busy} defaultOpen={busy} />
        ) : null}

        {message.steps && message.steps.length > 0 ? (
          <div
            className={cn(
              "space-y-2",
              (thinking || message.content || streaming) && "border-t border-border/60 pt-2",
            )}
          >
            {message.steps.map((step) => (
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

        {message.content || streaming ? (
          streaming ? (
            <div
              className={cn(
                "text-sm leading-relaxed",
                message.steps && message.steps.length > 0 && "border-t border-border/60 pt-2",
              )}
            >
              {message.content ? <MarkdownRenderer content={message.content} /> : null}
              {busy ? <TypewriterCursor /> : null}
            </div>
          ) : (
            <div
              className={cn(
                message.steps && message.steps.length > 0 && "border-t border-border/60 pt-2",
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
