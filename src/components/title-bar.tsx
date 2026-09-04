import type { HTMLAttributes, MouseEvent, ReactNode } from "react";
import type { DesktopPlatform } from "@/lib/window";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const APP_TITLE = "叮答";

export type TitleBarPlatform = DesktopPlatform;

export interface TitleBarProps extends HTMLAttributes<HTMLElement> {
  platform?: TitleBarPlatform;
  isMaximized?: boolean;
  actions?: ReactNode;
  onStartDrag?: () => void;
  onMinimize?: () => void;
  onToggleMaximize?: () => void;
  onClose?: () => void;
}

function IconMinus() {
  return (
    <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden>
      <path d="M3 8h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconSquare() {
  return (
    <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden>
      <rect x="3.5" y="3.5" width="9" height="9" rx="1" stroke="currentColor" strokeWidth="1.5" fill="none" />
    </svg>
  );
}

function IconRestore() {
  return (
    <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden>
      <rect x="5" y="2.5" width="8" height="8" rx="1" stroke="currentColor" strokeWidth="1.2" fill="none" />
      <rect x="2.5" y="5" width="8" height="8" rx="1" stroke="currentColor" strokeWidth="1.2" fill="none" />
    </svg>
  );
}

function IconClose() {
  return (
    <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden>
      <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function DragRegion({
  className,
  children,
  onStartDrag,
  onToggleMaximize,
}: {
  className?: string;
  children?: ReactNode;
  onStartDrag?: () => void;
  onToggleMaximize?: () => void;
}) {
  const handleMouseDown = (event: MouseEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    if (event.detail === 2) {
      onToggleMaximize?.();
      return;
    }
    onStartDrag?.();
  };

  return (
    <div
      data-tauri-drag-region
      className={cn("flex cursor-default items-center", className)}
      onMouseDown={handleMouseDown}
    >
      {children}
    </div>
  );
}

export function TitleBar({
  platform = "windows",
  isMaximized = false,
  actions,
  onStartDrag,
  onMinimize,
  onToggleMaximize,
  onClose,
  className,
  ...props
}: TitleBarProps) {
  const isMac = platform === "macos";

  const brand = (
    <div className="flex min-w-0 items-center gap-2.5">
      <img src="/logo-mark.svg" alt={APP_TITLE} className="size-5 shrink-0 rounded-[4px] object-cover" />
      <span className="truncate text-[15px] font-semibold tracking-wide text-foreground">{APP_TITLE}</span>
    </div>
  );

  const windowControls = (
    <div className="flex shrink-0">
      <Button variant="ghost" size="icon" className="h-11 w-[46px] rounded-none" onClick={onMinimize} aria-label="最小化">
        <IconMinus />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-11 w-[46px] rounded-none"
        onClick={onToggleMaximize}
        aria-label={isMaximized ? "还原" : "最大化"}
      >
        {isMaximized ? <IconRestore /> : <IconSquare />}
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-11 w-[46px] rounded-none hover:bg-[#c42b1c] hover:text-white"
        onClick={onClose}
        aria-label="关闭"
      >
        <IconClose />
      </Button>
    </div>
  );

  return (
    <header
      className={cn(
        "flex h-11 shrink-0 items-center select-none",
        "border-b border-border/30 bg-white/55 backdrop-blur-xl",
        "[-webkit-backdrop-filter:blur(20px)]",
        className,
      )}
      {...props}
    >
      {isMac ? (
        <>
          <div aria-hidden className="flex w-[4.5rem] shrink-0 items-center justify-center">
            <div className="size-3 rounded-full bg-muted" />
          </div>
          <DragRegion onStartDrag={onStartDrag} onToggleMaximize={onToggleMaximize} className="px-3">
            {brand}
          </DragRegion>
          <DragRegion onStartDrag={onStartDrag} onToggleMaximize={onToggleMaximize} className="min-w-8 flex-1 self-stretch" />
          {actions ? <div className="flex items-center gap-1 px-1">{actions}</div> : null}
          <div className="w-8 shrink-0" />
        </>
      ) : (
        <>
          <DragRegion onStartDrag={onStartDrag} onToggleMaximize={onToggleMaximize} className="px-3">
            {brand}
          </DragRegion>
          <DragRegion onStartDrag={onStartDrag} onToggleMaximize={onToggleMaximize} className="min-w-8 flex-1 self-stretch" />
          {actions ? <div className="flex items-center gap-1 px-1">{actions}</div> : null}
          {windowControls}
        </>
      )}
    </header>
  );
}
