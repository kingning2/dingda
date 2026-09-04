import type { ComposerAttachmentView } from "@/contracts/composer";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MessageAttachmentsProps {
  items: ComposerAttachmentView[];
  variant?: "user" | "assistant";
}

function MessageAttachments({ items, variant = "user" }: MessageAttachmentsProps) {
  if (items.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className={cn(
            "overflow-hidden rounded-lg border",
            variant === "user"
              ? "border-primary-foreground/20 bg-primary-foreground/10"
              : "border-border/80 bg-background/80",
          )}
        >
          {item.mime_type.startsWith("image/") ? (
            <img
              src={item.preview_url}
              alt={item.name}
              className="size-16 object-cover"
              draggable={false}
              loading="lazy"
              decoding="async"
            />
          ) : (
            <div className="flex size-16 items-center justify-center px-2 text-center text-[10px] opacity-90">
              {item.name}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

interface UserMessageProps {
  content: string;
  attachments?: ComposerAttachmentView[];
  className?: string;
}

export function UserMessage({ content, attachments, className }: UserMessageProps) {
  return (
    <Card
      size="sm"
      className={cn(
        "max-w-[92%] gap-2 overflow-visible bg-primary py-2.5 text-primary-foreground ring-primary/20",
        className,
      )}
    >
      <CardContent className="space-y-2 text-sm leading-relaxed">
        {attachments && attachments.length > 0 ? (
          <MessageAttachments items={attachments} variant="user" />
        ) : null}
        {content ? (
          <p className="whitespace-pre-wrap break-words">{content}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
