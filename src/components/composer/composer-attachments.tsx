import { X } from "lucide-react";
import type { ComposerAttachmentView } from "@/contracts/composer";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ComposerAttachmentsProps {
  items: ComposerAttachmentView[];
  onRemove: (id: string) => void;
  className?: string;
}

function isImageMime(mime: string): boolean {
  return mime.startsWith("image/");
}

export function ComposerAttachments({ items, onRemove, className }: ComposerAttachmentsProps) {
  if (items.length === 0) return null;

  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {items.map((item) => (
        <div
          key={item.id}
          className="group relative overflow-hidden rounded-lg border border-border/80 bg-muted/30"
        >
          {isImageMime(item.mime_type) ? (
            <img
              src={item.preview_url}
              alt={item.name}
              className="size-16 object-cover"
              draggable={false}
            />
          ) : (
            <div className="flex size-16 items-center justify-center px-2 text-center text-[10px] text-muted-foreground">
              {item.name}
            </div>
          )}
          <Button
            type="button"
            variant="secondary"
            size="icon-xs"
            className="absolute top-1 right-1 size-5 rounded-full opacity-90"
            aria-label={`移除 ${item.name}`}
            onClick={() => onRemove(item.id)}
          >
            <X className="size-3" />
          </Button>
        </div>
      ))}
    </div>
  );
}
