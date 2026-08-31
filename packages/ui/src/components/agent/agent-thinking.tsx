/**
 * AgentThinking — 展示 Agent 思考过程（不暴露内部分步结构）。
 */

import type { ReactNode } from "react";
import { Loader2 } from "../../icons";
import { cn } from "../../lib/cn";
import { SpotlightCard } from "../aceternity/spotlight-card";
import { Button } from "../button";

export type AgentThoughtStatus = "running" | "done" | "error";

export interface AgentThought {
  id: string;
  label: string;
  status: AgentThoughtStatus;
  detail?: ReactNode;
  /** 纯文本详情，供聊天区流式/渐进展示。 */
  detailText?: string;
  detailStreaming?: boolean;
}

export interface AgentThinkingProps {
  title?: string;
  thoughts: AgentThought[];
  message?: string;
  className?: string;
  onRestart?: () => void;
  controlsDisabled?: boolean;
}

function ThoughtStatus({ status }: { status: AgentThoughtStatus }) {
  if (status === "running") {
    return <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin text-primary" aria-hidden />;
  }
  if (status === "error") {
    return (
      <span
        className="mt-1.5 size-1.5 shrink-0 rounded-full bg-red-500"
        aria-hidden
      />
    );
  }
  return (
    <span
      className="mt-1.5 size-1.5 shrink-0 rounded-full bg-emerald-500/80"
      aria-hidden
    />
  );
}

export function AgentThinking({
  title = "思考过程",
  thoughts,
  message,
  className,
  onRestart,
  controlsDisabled,
}: AgentThinkingProps) {
  return (
    <SpotlightCard className={cn(className)}>
      <div className="rounded-[var(--radius-xl)] border border-border/70 bg-card p-4 shadow-sm">
        <div className="mb-3 flex items-start justify-between gap-2">
          <h3 className="font-medium text-foreground">{title}</h3>
          <div className="flex min-w-0 items-center gap-2">
            {message ? (
              <p className="max-w-[14rem] truncate text-right text-[length:var(--text-xs)] text-muted-foreground">
                {message}
              </p>
            ) : null}
            {onRestart ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={controlsDisabled}
                onClick={onRestart}
              >
                重新分析
              </Button>
            ) : null}
          </div>
        </div>

        {thoughts.length === 0 ? (
          <p className="text-[length:var(--text-sm)] text-muted-foreground">等待开始…</p>
        ) : (
          <ul className="space-y-4">
            {thoughts.map((thought, index) => (
              <li
                key={thought.id}
                className={cn(
                  "relative pl-4",
                  index < thoughts.length - 1 &&
                    "before:absolute before:top-4 before:bottom-[-1rem] before:left-[0.1875rem] before:w-px before:bg-border/70",
                )}
              >
                <div className="flex gap-2">
                  <ThoughtStatus status={thought.status} />
                  <div className="min-w-0 flex-1">
                    <p
                      className={cn(
                        "text-[length:var(--text-sm)]",
                        thought.status === "running" && "font-medium text-foreground",
                        thought.status === "done" && "text-foreground",
                        thought.status === "error" && "text-red-600",
                      )}
                    >
                      {thought.label}
                    </p>
                    {thought.detail ? (
                      <div className="mt-2 text-[length:var(--text-xs)] text-muted-foreground">
                        {thought.detail}
                      </div>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </SpotlightCard>
  );
}
