/**
 * 聊天气泡 + 输入区。
 */

import { ChevronDown, ChevronUp } from "@desk/ui/icons";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type CSSProperties,
  type KeyboardEvent,
} from "react";

import { CHAT_COPY } from "./copy";
import { useChatReady, useChatUnavailable } from "./provider";
import { chatStyles as s } from "./styles";
import { chatTokens as t } from "./tokens";
import { AssistantTurn } from "./turn";
import { useChat } from "./use-chat";

const FOLLOW_THRESHOLD = 24;

export function ChatPanel() {
  const ready = useChatReady();
  const unavailable = useChatUnavailable();
  const { messages, send, busy, error } = useChat();
  const [draft, setDraft] = useState("");
  const [sendHovered, setSendHovered] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const atBottomRef = useRef(true);
  const [atBottom, setAtBottom] = useState(true);

  const statusBanner = unavailable
    ? "副驾服务不可用，请稍后重试"
    : !ready
      ? "正在连接副驾服务…"
      : null;

  const syncAtBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) {
      return;
    }
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= FOLLOW_THRESHOLD + 1;
    atBottomRef.current = isAtBottom;
    setAtBottom(isAtBottom);
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    endRef.current?.scrollIntoView({ block: "end", behavior });
    atBottomRef.current = true;
    setAtBottom(true);
  }, []);

  useEffect(() => {
    if (atBottomRef.current) {
      scrollToBottom("smooth");
    }
  }, [messages, busy, scrollToBottom]);

  const canSend = ready && !busy && draft.trim().length > 0;

  const handleSend = () => {
    if (!canSend) {
      return;
    }
    send(draft);
    setDraft("");
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    handleSend();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const inputStyle: CSSProperties = {
    ...s.composerInput,
    ...(ready && !busy ? {} : { color: t.mutedFg, cursor: "not-allowed" }),
  };

  const hasRunActivity =
    busy || messages.some((item) => (item.runThoughts?.length ?? 0) > 0);
  const showWelcome = messages.length === 0 && !busy && !hasRunActivity;

  return (
    <div style={s.surface}>
      {statusBanner ? <p style={s.banner}>{statusBanner}</p> : null}

      <div ref={scrollRef} style={s.messages} onScroll={syncAtBottom}>
        <div style={s.column}>
          {showWelcome ? (
            <div style={s.welcome}>{CHAT_COPY.welcome}</div>
          ) : null}
          {messages.length > 0 ? (
            messages.map((message) =>
              message.role === "user" ? (
                <div key={message.id} style={s.userRow}>
                  <div style={s.userBubble}>{message.content}</div>
                </div>
              ) : (
                <AssistantTurn key={message.id} message={message} />
              ),
            )
          ) : null}
          <div ref={endRef} style={{ height: 1, flexShrink: 0 }} aria-hidden />
        </div>

        {!atBottom ? (
          <div style={s.toBottomSlot}>
            <button
              type="button"
              style={s.toBottomBtn}
              aria-label="回到底部"
              onClick={() => scrollToBottom()}
            >
              <ChevronDown className="size-4" aria-hidden />
            </button>
          </div>
        ) : null}
      </div>

      {error ? <p style={s.error}>{error}</p> : null}

      <form style={s.composer} onSubmit={handleSubmit}>
        <div style={s.composerCard}>
          <div style={s.composerScroll}>
            <textarea
              style={inputStyle}
              placeholder={CHAT_COPY.placeholder}
              rows={1}
              value={draft}
              disabled={!ready || busy}
              aria-label={CHAT_COPY.placeholder}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
            />
          </div>
          <div style={s.composerRow}>
            <button
              type="submit"
              style={s.composerSend(!canSend, sendHovered)}
              aria-label="发送"
              disabled={!canSend}
              onMouseEnter={() => setSendHovered(true)}
              onMouseLeave={() => setSendHovered(false)}
            >
              <ChevronUp className="size-4" aria-hidden />
            </button>
          </div>
        </div>
        <p style={s.disclaimer}>{CHAT_COPY.disclaimer}</p>
      </form>
    </div>
  );
}
