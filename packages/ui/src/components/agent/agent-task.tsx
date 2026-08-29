/**
 * AgentTask — Agent / 比价图步骤进度。
 */

import type { ReactNode } from "react";
import { Check, ChevronDown, Circle, Loader2, Play, X } from "../../icons";
import { cn } from "../../lib/cn";
import { Button } from "../button";
import { SpotlightCard } from "../aceternity/spotlight-card";

export type AgentTaskStepStatus = "pending" | "running" | "done" | "error";

export interface AgentTaskStep {
  id: string;
  label: string;
  status: AgentTaskStepStatus;
  /** 有值时可展开查看步骤详情。 */
  detail?: ReactNode;
  /** 从该步重跑（已跑过才有）。 */
  onSeek?: () => void;
}

export interface AgentTaskProps {
  title?: string;
  steps: AgentTaskStep[];
  message?: string;
  detail?: string;
  className?: string;
  onRestart?: () => void;
  controlsDisabled?: boolean;
}

function StepIcon({ status }: { status: AgentTaskStepStatus }) {
  if (status === "done") {
    return <Check className="size-3.5 text-emerald-600" aria-hidden />;
  }
  if (status === "error") {
    return <X className="size-3.5 text-red-600" aria-hidden />;
  }
  if (status === "running") {
    return <Loader2 className="size-3.5 animate-spin text-primary" aria-hidden />;
  }
  return <Circle className="size-3.5 text-muted-foreground/50" aria-hidden />;
}

function StepLabel({
  label,
  status,
}: {
  label: string;
  status: AgentTaskStepStatus;
}) {
  return (
    <span
      className={cn(
        "min-w-0 flex-1 truncate",
        status === "pending" && "text-muted-foreground",
        status === "running" && "font-medium text-foreground",
        status === "done" && "text-foreground",
        status === "error" && "text-red-600",
      )}
    >
      {label}
    </span>
  );
}

function SeekButton({
  disabled,
  onSeek,
}: {
  disabled?: boolean;
  onSeek: () => void;
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant="ghost"
      disabled={disabled}
      className="h-6 shrink-0 px-1.5 text-[length:var(--text-xs)] text-muted-foreground"
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onSeek();
      }}
    >
      <Play className="size-3" aria-hidden />
      从这步
    </Button>
  );
}

export function AgentTask({
  title = "执行步骤",
  steps,
  message,
  detail,
  className,
  onRestart,
  controlsDisabled,
}: AgentTaskProps) {
  return (
    <SpotlightCard className={cn(className)}>
      <div className="rounded-[var(--radius-xl)] border border-border/70 bg-card p-4 shadow-sm">
        <div className="mb-3 flex items-start justify-between gap-2">
          <h3 className="font-medium text-foreground">{title}</h3>
          <div className="flex min-w-0 items-center gap-2">
            {message ? (
              <p className="max-w-[12rem] truncate text-right text-[length:var(--text-xs)] text-muted-foreground">
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
                从头重跑
              </Button>
            ) : null}
          </div>
        </div>
        <ol className="space-y-2">
          {steps.map((step) => {
            const rowClass = cn(
              "rounded-[var(--radius-md)] px-2 py-1.5 text-[length:var(--text-sm)]",
              step.status === "running" && "bg-primary/5",
              step.status === "error" && "bg-red-500/5",
            );
            const seek =
              step.onSeek != null ? (
                <SeekButton disabled={controlsDisabled} onSeek={step.onSeek} />
              ) : null;

            if (step.detail == null) {
              return (
                <li key={step.id} className={cn("flex items-center gap-2", rowClass)}>
                  <StepIcon status={step.status} />
                  <StepLabel label={step.label} status={step.status} />
                  {seek}
                </li>
              );
            }

            return (
              <li key={step.id} className={rowClass}>
                <details
                  className="group"
                  ref={(el) => {
                    // React 无 defaultOpen；挂载时按当前步骤状态设初始展开，此后保持非受控。
                    if (el) el.open = step.status === "running";
                  }}
                >
                  <summary className="flex cursor-pointer list-none items-center gap-2 [&::-webkit-details-marker]:hidden">
                    <StepIcon status={step.status} />
                    <StepLabel label={step.label} status={step.status} />
                    {seek}
                    <ChevronDown
                      className="size-3.5 shrink-0 text-muted-foreground transition-transform duration-150 group-open:rotate-180"
                      aria-hidden
                    />
                  </summary>
                  <div className="mt-2 ml-5 border-l border-border/60 pl-3 text-[length:var(--text-xs)] text-muted-foreground">
                    {step.detail}
                  </div>
                </details>
              </li>
            );
          })}
        </ol>
        {detail ? (
          <p className="mt-3 border-t border-border/60 pt-2 text-[length:var(--text-xs)] text-muted-foreground">
            {detail}
          </p>
        ) : null}
      </div>
    </SpotlightCard>
  );
}
