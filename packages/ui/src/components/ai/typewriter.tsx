/**
 * TypewriterText — 流式时展示已到达正文 + 光标；不积压等整段。
 */

import { cn } from "../../lib/cn";

export function TypewriterText({
  text,
  streaming = false,
  className,
}: {
  text: string;
  streaming?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("whitespace-pre-wrap", className)}>
      {text}
      {streaming ? (
        <span
          className="ml-px inline-block h-[1em] w-[0.45ch] translate-y-px animate-pulse bg-foreground/70"
          aria-hidden
        />
      ) : null}
    </span>
  );
}
