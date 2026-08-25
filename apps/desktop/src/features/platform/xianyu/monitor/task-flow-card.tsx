import { cn, SpotlightCard } from "@desk/ui";
import { Play, Star } from "@desk/ui/icons";
import type { MonitorTask } from "@desk/platform/ipc/xianyu-monitor";
import {
  FLOW_GRADIENTS,
  formatMonitorTime,
  taskGradientIndex,
  taskShortCode,
  taskStatusLabel,
} from "./monitor-utils";

export interface TaskFlowCardProps {
  task: MonitorTask;
  onSelect: () => void;
  onRun: () => void;
}

/** 单个监控任务卡片 — 参考 Shadcn Admin project-list-1。 */
export function TaskFlowCard({ task, onSelect, onRun }: TaskFlowCardProps) {
  const gradient = FLOW_GRADIENTS[taskGradientIndex(task.id)];

  return (
    <SpotlightCard lift={false} className="h-full">
      <article
        className="flex h-full flex-col overflow-hidden rounded-[var(--radius-xl)] border border-border/70 bg-card transition-colors hover:border-border"
      >
        <div className={cn("relative h-28 bg-gradient-to-br", gradient)}>
          <button
            type="button"
            className="absolute inset-0 z-0"
            aria-label={`查看 ${task.name}`}
            onClick={onSelect}
          />
          <span className="pointer-events-none absolute left-3 top-3 z-10 rounded-full border border-border/60 bg-background/80 px-2 py-0.5 text-[10px] font-medium backdrop-blur-sm">
            {taskStatusLabel(task)}
          </span>
          <button
            type="button"
            className="absolute right-3 top-3 z-10 rounded-md border border-border/60 bg-background/70 p-1 backdrop-blur-sm transition-colors hover:bg-background"
            aria-label="立即运行"
            onClick={(event) => {
              event.stopPropagation();
              onRun();
            }}
          >
            <Play className="size-3.5" aria-hidden />
          </button>
        </div>

        <button type="button" className="flex flex-1 flex-col text-left" onClick={onSelect}>
          <div className="space-y-3 p-4">
            <div>
              <div className="flex items-center gap-2 text-[length:var(--text-xs)] text-muted-foreground">
                <span className="font-mono">{taskShortCode(task.id)}</span>
                {task.enabled ? (
                  <Star className="size-3 text-amber-500/80" aria-hidden />
                ) : null}
              </div>
              <h3 className="mt-1 line-clamp-2 text-[length:var(--text-sm)] font-semibold text-foreground">
                {task.name}
              </h3>
            </div>

            <div className="flex items-center justify-between gap-2 text-[length:var(--text-xs)]">
              <span className="text-muted-foreground">监控周期</span>
              <span className="font-medium text-foreground">每 {task.intervalMinutes} 分钟</span>
            </div>

            <p className="line-clamp-2 text-[length:var(--text-xs)] leading-relaxed text-muted-foreground">
              {task.intent}
            </p>
          </div>
        </button>

        <div className="mt-auto border-t border-border/70 px-4 py-3">
          <div className="flex items-center justify-between gap-3 text-[length:var(--text-xs)]">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">上次运行</p>
              <p className="mt-0.5 font-semibold tabular-nums text-foreground">
                {formatMonitorTime(task.lastRunAt)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">关键词</p>
              <p className="mt-0.5 font-semibold tabular-nums text-foreground">{task.keywords.length}</p>
            </div>
          </div>
        </div>
      </article>
    </SpotlightCard>
  );
}
