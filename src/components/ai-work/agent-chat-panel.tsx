import { memo, useEffect, useRef } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import type { ComposerAgentOption, ComposerSubmitPayload } from "@/contracts/composer";
import type { AgentWorkDetailView, AgentWorkStepView } from "@/contracts/ai-work";
import { AIMessage, UserMessage, useMessageTypewriter } from "@/components/ai";
import { PromptComposer } from "@/components/composer";
import { useComposerAgentOptions } from "@/components/composer/composer-agents";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { productsForStep, resolveStepPageUrl } from "./work-step-utils";
import { WorkStatusBadge } from "./work-status-badge";
import { cn } from "@/lib/utils";

interface AgentChatPanelProps {
  detail: AgentWorkDetailView;
  busy?: boolean;
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
}

const ChatComposerFooter = memo(function ChatComposerFooter({
  agents,
  defaultAgentId,
  defaultModelId,
  placeholder,
  disabled,
  busy,
  onSend,
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
          />
        </CardContent>
      </Card>
    </footer>
  );
});

export function AgentChatPanel({
  detail,
  busy = false,
  selectedStepId = null,
  onBack,
  onSend,
  onSelectStep,
}: AgentChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollMetricsRef = useRef({ messageCount: 0, productCount: 0 });
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

  useEffect(() => {
    const prev = scrollMetricsRef.current;
    const contentGrew =
      messageCount > prev.messageCount ||
      productCount > prev.productCount ||
      (busy && (lastAssistantContentLength > 0 || lastAssistantThinkingLength > 0));
    scrollMetricsRef.current = { messageCount, productCount };

    if (!contentGrew && !busy) return;

    bottomRef.current?.scrollIntoView({
      behavior: busy ? "auto" : "smooth",
      block: "end",
    });
  }, [messageCount, productCount, busy, lastAssistantContentLength, lastAssistantThinkingLength]);

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

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-4 px-4 py-4">
          <div className="space-y-4">
            {detail.messages.map((message) => (
              <div
                key={message.id}
                className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}
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
          {busy ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Agent 执行中…
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      <ChatComposerFooter
        agents={composerAgents}
        defaultAgentId={detail.composer_agent_id}
        defaultModelId={detail.composer_model_id}
        placeholder={detail.composer_placeholder}
        disabled={!detail.can_send}
        busy={busy}
        onSend={onSend}
      />
    </div>
  );
}
