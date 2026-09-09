/**
 * 用户消息块：像 Cursor 一样的输入框外观，可点开编辑并从该处重新生成。
 */

import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";
import type { ComposerAttachmentView } from "@/contracts/composer";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export interface UserBlockProps {
  content: string;
  attachments?: ComposerAttachmentView[];
  /** 忙碌时不可编辑。 */
  editable?: boolean;
  /** 提交编辑：从该条截断并重新跑。 */
  onResubmit?: (content: string) => void;
}

export function UserBlock({
  content,
  attachments,
  editable = true,
  onResubmit,
}: UserBlockProps) {
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
      <div className="rounded-2xl border border-border/80 bg-muted/40 p-3 shadow-sm">
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
        "w-full rounded-2xl border border-border/80 bg-muted/40 px-3.5 py-2.5 text-left shadow-sm",
        "transition-colors",
        editable && onResubmit
          ? "cursor-text hover:border-border hover:bg-muted/55"
          : "cursor-default",
      )}
      aria-label="编辑消息并从此处重新生成"
    >
      {attachmentRow}
      {content ? (
        <p className="whitespace-pre-wrap break-words text-[14px] font-medium leading-relaxed text-foreground">
          {content}
        </p>
      ) : (
        <p className="text-[13px] text-muted-foreground">空消息</p>
      )}
    </button>
  );
}
