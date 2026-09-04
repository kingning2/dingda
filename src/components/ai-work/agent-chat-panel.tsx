import { memo, useCallback, useEffect, useRef } from "react";
import { ArrowLeft } from "lucide-react";
import type { ComposerAgentOption, ComposerSubmitPayload } from "@/contracts/composer";
import type { AgentWorkDetailView, AgentWorkStepView } from "@/contracts/ai-work";
import { AIMessage, UserMessage, useMessageTypewriter } from "@/components/ai";
import { PromptComposer } from "@/components/composer";
import { useComposerAgentOptions } from "@/components/composer/composer-agents";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { productsForStep, resolveStepPageUrl } from "./work-step-utils";
import { WorkStatusBadge } from "./work-status-badge";
import { cn } from "@/lib/utils";

interface AgentChatPanelProps {
  detail: AgentWorkDetailView;
  busy?: boolean;
  error?: string | null;
  selectedStepId?: string | null;
  onBack?: () => void;
  onSend?: (payload: ComposerSubmitPayload) => void;
  onSelectStep?: (step: AgentWorkStepView) => void;
}

interface ChatComposerFooterProps {
  agents: ComposerAgentOption[];
  defaultAgentId?: string | null;
  defaultModelId?: string | null;
  placeholder?: string | null;
  disabled: boolean;
  busy: boolean;
  onSend?: (payload: ComposerSubmitPayload) => void;
  onInputActivity?: () => void;
}

const ChatComposerFooter = memo(function ChatComposerFooter({
  agents,
  defaultAgentId,
  defaultModelId,
  placeholder,
  disabled,
  busy,
  onSend,
  onInputActivity,
}: ChatComposerFooterProps) {
  return (
    <footer className="shrink-0 border-t border-border/70 p-3">
      <Card size="sm" className="gap-0 py-2 shadow-sm">
        <CardContent className="px-3 pb-2 pt-2">
          <PromptComposer
            agents={agents}
            defaultAgentId={defaultAgentId}
            defaultModelId={defaultModelId}
            placeholder={placeholder ?? "输入补充指令…"}
            disabled={disabled}
            busy={busy}
            minRows={3}
            textareaClassName="min-h-[72px] text-sm"
            onSubmit={(payload) => onSend?.(payload)}
            onInputActivity={onInputActivity}
          />
        </CardContent>
      </Card>
    </footer>
  );
});

export function AgentChatPanel({
  detail,
  busy = false,
  error = null,
  selectedStepId = null,
  onBack,
  onSend,
  onSelectStep,
}: AgentChatPanelProps) {
  const scrollViewportRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollMetricsRef = useRef({ messageCount: 0, productCount: 0, contentLen: 0 });
  const liveAgents = useComposerAgentOptions();
  const { shouldTypewriter, markTypewriterComplete } = useMessageTypewriter(
    detail.work_id,
    detail.messages,
  );
  const composerAgents =
    detail.composer_agents.length > 0 ? detail.composer_agents : liveAgents;

  const messageCount = detail.messages.length;
  const productCount = detail.products.items.length;
  const lastAssistant = [...detail.messages].reverse().find((message) => message.role === "assistant");
  const lastAssistantContentLength = lastAssistant?.content.length ?? 0;
  const lastAssistantThinkingLength = lastAssistant?.thinking?.length ?? 0;
  const lastAssistantSteps = lastAssistant?.steps?.length ?? 0;
  const contentFingerprint =
    lastAssistantContentLength + lastAssistantThinkingLength + lastAssistantSteps;

  const scrollToBottom = useCallback(() => {
    const viewport = scrollViewportRef.current;
    if (viewport) {
      viewport.scrollTop = viewport.scrollHeight;
      return;
    }
    bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, []);

  useEffect(() => {
    const prev = scrollMetricsRef.current;
    const contentGrew =
      messageCount > prev.messageCount ||
      productCount > prev.productCount ||
      contentFingerprint > prev.contentLen ||
      busy;
    scrollMetricsRef.current = {
      messageCount,
      productCount,
      contentLen: contentFingerprint,
    };

    if (!contentGrew) return;

    const frame = window.requestAnimationFrame(scrollToBottom);
    return () => window.cancelAnimationFrame(frame);
  }, [messageCount, productCount, busy, contentFingerprint, scrollToBottom]);

  const lastAssistantMessageId = [...detail.messages]
    .reverse()
    .find((message) => message.role === "assistant")?.id;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border/70 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <Button variant="ghost" size="icon-sm" onClick={onBack} aria-label="返回">
            <ArrowLeft className="size-4" />
          </Button>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold text-foreground">{detail.title}</h1>
            <p className="truncate text-xs text-muted-foreground">AI 工作 · {detail.work_id}</p>
          </div>
        </div>
        <WorkStatusBadge
          label={detail.status.label}
          badgeClass={detail.status.badge_class}
          hint={detail.status.hint}
        />
      </header>

      <div ref={scrollViewportRef} className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-4 px-4 py-4">
          <div className="space-y-4">
            {detail.messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "flex min-w-0",
                  message.role === "user" ? "justify-end" : "justify-start",
                )}
              >
                {message.role === "user" ? (
                  <UserMessage content={message.content} attachments={message.attachments} />
                ) : (
                  <AIMessage
                    message={message}
                    busy={busy && message.id === lastAssistantMessageId}
                    thinking={message.thinking}
                    streaming={busy && message.id === lastAssistantMessageId}
                    typewriterActive={shouldTypewriter(message)}
                    onTypewriterComplete={() => markTypewriterComplete(message.id)}
                    selectedStepId={selectedStepId}
                    resolveStepPageUrl={(step) => resolveStepPageUrl(detail, step)}
                    productsForStep={(stepId) => productsForStep(detail.products.items, stepId)}
                    onSelectStep={onSelectStep}
                  />
                )}
              </div>
            ))}
          </div>
          {error ? (
            <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          ) : null}
          <div ref={bottomRef} />
        </div>
      </div>

      <ChatComposerFooter
        agents={composerAgents}
        defaultAgentId={detail.composer_agent_id}
        defaultModelId={detail.composer_model_id}
        placeholder={detail.composer_placeholder}
        disabled={!detail.can_send}
        busy={busy}
        onSend={onSend}
        onInputActivity={() => {
          window.requestAnimationFrame(scrollToBottom);
        }}
      />
    </div>
  );
}
