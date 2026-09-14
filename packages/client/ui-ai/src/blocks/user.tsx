/**
 * 用户消息块：像 Cursor 一样的输入框外观，可点开编辑并从该处重新生成。
 *
 * 职责：
 *   渲染一条用户消息（user 块），支持就地编辑并从该条截断重新生成。
 *
 * 设计说明：
 *   - 可编辑性来自上下文（活回合不可编辑），块自己不判断运行状态。
 *   - 上下文回调收的是 (messageId, content)，块在这里把 messageId 绑上 ——
 *     块不需要知道「我是哪条消息」以外的任何事。
 *   - 文件末尾自注册，Chat 通过注册表取用，不认识本组件。
 */

import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";
import { Button } from "@v2/ui-primitives/button";
import { Textarea } from "@v2/ui-primitives/textarea";
import { cn } from "@v2/ui-primitives/utils";
import { registerBlock } from "../chat/registry";
import type { ChatBlockProps } from "../chat/types";

/** 用户块：用户消息的渲染，含重发按钮。 */
export function UserBlock({ block, context }: ChatBlockProps<"user">) {
  const { content, attachments, messageId } = block;
  const resubmit = context.onResubmitUser;
  const editable = !context.busy;
  const onResubmit = resubmit ? (next: string) => resubmit(messageId, next) : undefined;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!editing) setDraft(content);
  }, [content, editing]);

  useEffect(() => {
    if (!editing) return;
    const el = textareaRef.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
    el.style.height = "auto";
    el.style.height = `${Math.max(40, el.scrollHeight)}px`;
  }, [editing]);

  function commit() {
    const next = draft.trim();
    if (!next) return;
    setEditing(false);
    onResubmit?.(next);
  }

  function cancel() {
    setDraft(content);
    setEditing(false);
  }

  const attachmentRow =
    attachments && attachments.length > 0 ? (
      <div className="mb-2 flex flex-wrap gap-2">
        {attachments.map((item) => (
          <div
            key={item.id}
            className="overflow-hidden rounded-md border border-border/70 bg-muted/40"
          >
            {item.mime_type.startsWith("image/") ? (
              <img
                src={item.preview_url}
                alt={item.name}
                className="size-14 object-cover"
                draggable={false}
                loading="lazy"
                decoding="async"
              />
            ) : (
              <div className="flex size-14 items-center justify-center px-1 text-center text-[10px] text-muted-foreground">
                {item.name}
              </div>
            )}
          </div>
        ))}
      </div>
    ) : null;

  if (editing) {
    return (
      <div className="grid grid-cols-[1rem_minmax(0,1fr)] gap-2 rounded-[4px] bg-foreground/[0.04] px-3 py-2.5">
        <span className="pt-px font-semibold leading-relaxed text-muted-foreground">›</span>
        <div className="min-w-0">
          {attachmentRow}
          <Textarea
            ref={textareaRef}
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              const el = event.target;
              el.style.height = "auto";
              el.style.height = `${Math.max(40, el.scrollHeight)}px`;
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                cancel();
                return;
              }
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (draft.trim()) commit();
              }
            }}
            className="min-h-[40px] resize-none border-0 bg-transparent px-0 py-0 text-[14px] font-medium shadow-none focus-visible:ring-0"
            rows={1}
          />
          <div className="mt-2 flex items-center justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={cancel}>
              取消
            </Button>
            <Button
              type="button"
              size="icon-sm"
              className="rounded-full"
              disabled={!draft.trim()}
              onClick={commit}
              aria-label="从此处重新生成"
            >
              <ArrowUp className="size-4" />
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <button
      type="button"
      disabled={!editable || !onResubmit}
      onClick={() => {
        if (!editable || !onResubmit) return;
        setEditing(true);
      }}
      className={cn(
        "w-full rounded-[4px] bg-foreground/[0.04] px-3 py-2.5 text-left",
        "transition-colors",
        editable && onResubmit
          ? "cursor-text hover:bg-foreground/[0.065]"
          : "cursor-default",
      )}
      aria-label="编辑消息并从此处重新生成"
    >
      <div className="w-full">
        {attachmentRow}
        {content ? (
          <p className="whitespace-pre-wrap break-words text-[14px] font-medium leading-relaxed text-foreground">
            {content}
          </p>
        ) : (
          <p className="text-[13px] text-muted-foreground">空消息</p>
        )}
      </div>
    </button>
  );
}

registerBlock("user", UserBlock);
