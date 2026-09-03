import { useCallback, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

const MIN_CHAT_WIDTH = 320;
const MAX_CHAT_WIDTH = 560;
const DEFAULT_CHAT_WIDTH = 420;
const HANDLE_WIDTH = 8;

interface AiWorkSplitProps {
  chat: ReactNode;
  workspace: ReactNode;
  className?: string;
}

export function AiWorkSplit({ chat, workspace, className }: AiWorkSplitProps) {
  const splitRef = useRef<HTMLDivElement>(null);
  const [chatWidth, setChatWidth] = useState(DEFAULT_CHAT_WIDTH);
  const [resizing, setResizing] = useState(false);

  const clampWidth = useCallback((width: number) => {
    const splitWidth = splitRef.current?.clientWidth ?? window.innerWidth;
    const max = Math.min(MAX_CHAT_WIDTH, splitWidth - HANDLE_WIDTH - 360);
    return Math.max(MIN_CHAT_WIDTH, Math.min(width, max));
  }, []);

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = chatWidth;
      setResizing(true);

      const onMove = (moveEvent: globalThis.PointerEvent) => {
        const delta = moveEvent.clientX - startX;
        setChatWidth(clampWidth(startWidth + delta));
      };

      const onUp = () => {
        setResizing(false);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [chatWidth, clampWidth],
  );

  return (
    <div
      ref={splitRef}
      className={cn(
        "grid h-full min-h-0 min-w-0 overflow-hidden bg-[color-mix(in_srgb,var(--bg-panel)_72%,transparent)]",
        resizing && "cursor-col-resize select-none",
        className,
      )}
      style={{
        gridTemplateColumns: `${chatWidth}px ${HANDLE_WIDTH}px minmax(360px, 1fr)`,
      }}
    >
      <div className="flex min-h-0 min-w-0 flex-col overflow-hidden border-r border-border/70 bg-card">
        {chat}
      </div>

      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="调整聊天面板宽度"
        className={cn(
          "relative z-10 min-h-0 cursor-col-resize bg-transparent",
          "before:absolute before:inset-y-0 before:left-1/2 before:w-px before:-translate-x-1/2 before:bg-border",
          "hover:before:bg-foreground/25",
        )}
        onPointerDown={handlePointerDown}
      />

      <div className="flex min-h-0 min-w-0 flex-col overflow-hidden bg-background">{workspace}</div>
    </div>
  );
}
