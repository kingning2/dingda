import { cn } from "@desk/ui";
import { Check, Loader2 } from "@desk/ui/icons";
import type { MonitorProgressStage } from "@desk/platform/events";
import type { MonitorRun, MonitorTask } from "@desk/platform/ipc/xianyu-monitor";

export const MONITOR_FLOW_STEPS = [
  { id: "keywords", label: "AI 关键词", stages: ["keywords"] as MonitorProgressStage[] },
  { id: "search", label: "闲鱼搜索", stages: ["search", "scanned"] as MonitorProgressStage[] },
  { id: "decide", label: "AI 决策", stages: ["decide"] as MonitorProgressStage[] },
  { id: "store", label: "结果落库", stages: ["matched", "finished"] as MonitorProgressStage[] },
] as const;

function stageIndex(stage: MonitorProgressStage): number {
  for (let i = 0; i < MONITOR_FLOW_STEPS.length; i += 1) {
    if (MONITOR_FLOW_STEPS[i]!.stages.includes(stage)) {
      return i;
    }
  }
  if (stage === "started") {
    return 0;
  }
  if (stage === "failed") {
    return MONITOR_FLOW_STEPS.length - 1;
  }
  return -1;
}

function resolveStepState(
  stepIndex: number,
  task: MonitorTask,
  latestRun: MonitorRun | null | undefined,
): "done" | "active" | "pending" | "failed" {
  if (latestRun?.status === "failed") {
    const failedAt = latestRun.steps.length
      ? stageIndex(latestRun.steps[latestRun.steps.length - 1]!.stage)
      : -1;
    if (stepIndex < failedAt) {
      return "done";
    }
    if (stepIndex === failedAt) {
      return "failed";
    }
    return "pending";
  }

  if (task.isRunning || latestRun?.status === "running") {
    const activeStage =
      latestRun?.steps.length && latestRun.steps.length > 0
        ? latestRun.steps[latestRun.steps.length - 1]!.stage
        : "started";
    const activeIndex = stageIndex(activeStage);
    if (stepIndex < activeIndex) {
      return "done";
    }
    if (stepIndex === activeIndex) {
      return "active";
    }
    return "pending";
  }

  if (latestRun?.status === "success") {
    return "done";
  }

  return "pending";
}

export interface MonitorFlowPipelineProps {
  task: MonitorTask;
  latestRun?: MonitorRun | null;
  compact?: boolean;
  className?: string;
}

/** 监控四步流程可视化 — 关键词 → 搜索 → 决策 → 落库。 */
export function MonitorFlowPipeline({
  task,
  latestRun,
  compact = false,
  className,
}: MonitorFlowPipelineProps) {
  return (
    <ol
      className={cn(
        "grid gap-2",
        compact ? "grid-cols-4" : "sm:grid-cols-2 lg:grid-cols-4",
        className,
      )}
    >
      {MONITOR_FLOW_STEPS.map((step, index) => {
        const state = resolveStepState(index, task, latestRun);
        return (
          <li key={step.id} className="relative">
            {index < MONITOR_FLOW_STEPS.length - 1 && !compact ? (
              <span
                className="absolute left-[calc(50%+1.25rem)] top-5 hidden h-px w-[calc(100%-2.5rem)] bg-border lg:block"
                aria-hidden
              />
            ) : null}
            <div
              className={cn(
                "relative rounded-[var(--radius-lg)] border p-3 transition-colors",
                state === "done" && "border-emerald-500/30 bg-emerald-500/5",
                state === "active" && "border-primary/40 bg-primary/5",
                state === "failed" && "border-destructive/40 bg-destructive/5",
                state === "pending" && "border-border/70 bg-muted/20",
              )}
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "flex size-7 shrink-0 items-center justify-center rounded-full border text-[length:var(--text-xs)] font-medium",
                    state === "done" && "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
                    state === "active" && "border-primary/40 bg-primary/10 text-primary",
                    state === "failed" && "border-destructive/40 bg-destructive/10 text-destructive",
                    state === "pending" && "border-border bg-muted/40 text-muted-foreground",
                  )}
                >
                  {state === "active" ? (
                    <Loader2 className="size-3.5 animate-spin" aria-hidden />
                  ) : state === "done" ? (
                    <Check className="size-3.5" aria-hidden />
                  ) : (
                    index + 1
                  )}
                </span>
                <div className="min-w-0">
                  <p className="text-[length:var(--text-xs)] font-medium text-foreground">
                    {step.label}
                  </p>
                  {!compact ? (
                    <p className="text-[10px] text-muted-foreground">
                      {state === "done"
                        ? "已完成"
                        : state === "active"
                          ? "进行中"
                          : state === "failed"
                            ? "失败"
                            : "待执行"}
                    </p>
                  ) : null}
                </div>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
