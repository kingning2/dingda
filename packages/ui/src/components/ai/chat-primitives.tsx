/**
 * Chat Bubble / Message / Marker — desk 风格轻量原语。
 */

import * as React from "react";

import { cn } from "../../lib/cn";

export function ChatMessage({
  role,
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { role: "user" | "assistant" | "system" }) {
  return (
    <div
      data-role={role}
      className={cn(
        "flex w-full",
        role === "user" ? "justify-end" : "justify-start",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function ChatBubble({
  role = "assistant",
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { role?: "user" | "assistant" }) {
  return (
    <div
      className={cn(
        "max-w-[85%] rounded-[var(--radius-lg)] px-3 py-2 text-[length:var(--text-sm)] leading-relaxed",
        role === "user"
          ? "bg-primary text-primary-foreground"
          : "border border-border/70 bg-card text-foreground",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function ChatMarker({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "my-1 flex items-center justify-center text-[length:var(--text-xs)] text-muted-foreground",
        className,
      )}
      {...props}
    >
      <span className="rounded-full border border-border/60 bg-muted/40 px-2 py-0.5">
        {children}
      </span>
    </div>
  );
}
