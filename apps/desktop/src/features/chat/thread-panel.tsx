import { useEffect, useRef, useState } from "react";
import {
  AsyncButton,
  Button,
  IconButton,
  ScrollArea,
  Textarea,
  toast,
} from "@desk/ui";
import {
  MessageSquare,
  PanelRightClose,
  PanelRightOpen,
  Send,
} from "@desk/ui/icons";
import type { ChannelConversation, ChannelMessage } from "@desk/contracts";
import { ConversationAvatar } from "./conversation-avatar";
import { conversationSubject, formatChatTime } from "./format";

export interface ThreadPanelProps {
  selectedConversation: ChannelConversation | null;
  peerName: string;
  accountLabel: string;
  threadMessages: ChannelMessage[];
  error: string | null;
  infoOpen: boolean;
  needsReply: boolean;
  draft: string;
  onDraftChange: (value: string) => void;
  onToggleInfo: () => void;
  onSend: (text: string) => Promise<void>;
}

function senderLabel(message: ChannelMessage, peerName: string, accountLabel: string): string {
  if (message.direction === "out") {
    return message.sender === "human" ? accountLabel : message.sender;
  }
  return peerName;
}

/** 会话消息区（中栏）— 参考 Shadcn Admin inbox-1 邮件线程 + 回复框。 */
export function ThreadPanel({
  selectedConversation,
  peerName,
  accountLabel,
  threadMessages,
  error,
  infoOpen,
  needsReply,
  draft,
  onDraftChange,
  onToggleInfo,
  onSend,
}: ThreadPanelProps) {
  const [sending, setSending] = useState(false);
  const threadEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [threadMessages]);

  useEffect(() => {
    onDraftChange("");
  }, [selectedConversation?.id, onDraftChange]);

  async function handleSend() {
    if (!draft.trim()) {
      return;
    }
    setSending(true);
    try {
      await onSend(draft);
      onDraftChange("");
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "发送失败");
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void handleSend();
    }
  }

  const subject = selectedConversation ? conversationSubject(selectedConversation) : "";

  return (
    <section className="flex min-w-0 flex-1 flex-col bg-transparent">
      {!selectedConversation ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <MessageSquare className="size-10 opacity-30" aria-hidden />
          <p className="text-[length:var(--text-sm)]">选择左侧会话查看消息</p>
        </div>
      ) : (
        <>
          <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate text-[length:var(--text-sm)] font-semibold text-foreground">
                  {subject}
                </h2>
                {needsReply ? (
                  <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[length:var(--text-xs)] text-emerald-600 dark:text-emerald-400">
                    待回复
                  </span>
                ) : (
                  <span className="rounded-full border border-border bg-muted/50 px-2 py-0.5 text-[length:var(--text-xs)] text-muted-foreground">
                    已读
                  </span>
                )}
              </div>
              <p className="mt-0.5 truncate text-[length:var(--text-xs)] text-muted-foreground">
                {peerName} · {accountLabel}
              </p>
            </div>
            <IconButton
              label={infoOpen ? "收起客户信息" : "展开客户信息"}
              onClick={onToggleInfo}
              className="shrink-0"
            >
              {infoOpen ? (
                <PanelRightClose className="size-4" aria-hidden />
              ) : (
                <PanelRightOpen className="size-4" aria-hidden />
              )}
            </IconButton>
          </header>

          <ScrollArea className="min-h-0 flex-1">
            <div className="space-y-4 px-4 py-4">
              {threadMessages.length === 0 ? (
                <p className="py-8 text-center text-[length:var(--text-sm)] text-muted-foreground">
                  该会话还没有消息记录
                </p>
              ) : (
                threadMessages.map((message) => {
                  const outbound = message.direction === "out";
                  const name = senderLabel(message, peerName, accountLabel);
                  return (
                    <article
                      key={message.id}
                      className="rounded-[var(--radius-lg)] border border-border/80 bg-card p-4 shadow-sm"
                    >
                      <div className="flex items-start gap-3">
                        <ConversationAvatar name={name} size="md" />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-[length:var(--text-sm)] text-foreground">
                              {name}
                            </span>
                            {outbound ? (
                              <span className="rounded-md border border-border bg-muted/50 px-1.5 py-0.5 text-[length:var(--text-xs)] text-muted-foreground">
                                客服
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-0.5 text-[length:var(--text-xs)] text-muted-foreground">
                            {outbound ? `发送至 ${peerName}` : `来自 ${peerName}`}
                          </p>
                          <p className="text-[length:var(--text-xs)] text-muted-foreground/80">
                            {formatChatTime(message.created_at)}
                          </p>
                        </div>
                      </div>
                      <p className="mt-3 whitespace-pre-wrap break-words text-[length:var(--text-sm)] leading-relaxed text-foreground">
                        {message.content}
                      </p>
                    </article>
                  );
                })
              )}
              <div ref={threadEndRef} />
            </div>
          </ScrollArea>

          <footer className="border-t border-border bg-muted/10 p-4">
            {error ? (
              <p className="mb-2 text-[length:var(--text-xs)] text-destructive">{error}</p>
            ) : null}
            <div className="overflow-hidden rounded-[var(--radius-lg)] border border-border bg-card shadow-sm">
              <div className="flex items-center justify-between gap-2 border-b border-border/80 px-3 py-2">
                <p className="truncate text-[length:var(--text-xs)] text-muted-foreground">
                  回复 <span className="font-medium text-foreground">{peerName}</span>
                </p>
                <span className="shrink-0 text-[length:var(--text-xs)] text-muted-foreground/70">
                  Ctrl+Enter 发送
                </span>
              </div>
              <Textarea
                value={draft}
                onChange={(event) => onDraftChange(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="撰写回复…"
                rows={4}
                className="min-h-[6rem] resize-none rounded-none border-0 bg-transparent shadow-none focus-visible:ring-0"
              />
              <div className="flex items-center justify-end gap-2 border-t border-border/80 px-3 py-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={!draft.trim()}
                  onClick={() => onDraftChange("")}
                >
                  清空
                </Button>
                <AsyncButton
                  size="sm"
                  loading={sending}
                  disabled={!draft.trim()}
                  onClick={() => handleSend()}
                >
                  <Send className="size-3.5" aria-hidden />
                  发送
                </AsyncButton>
              </div>
            </div>
          </footer>
        </>
      )}
    </section>
  );
}
