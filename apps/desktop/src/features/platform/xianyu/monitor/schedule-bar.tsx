import { AsyncButton, Button, Progress } from "@desk/ui";
import { Clock, CirclePause, Play } from "@desk/ui/icons";
import type { MonitorTask } from "@desk/platform/ipc/xianyu-monitor";
import { formatScheduleCountdown, useScheduleCountdown } from "./schedule-utils";

export interface MonitorScheduleBarProps {
  task: MonitorTask;
  pausing?: boolean;
  resuming?: boolean;
  onPause: () => void;
  onResume: () => void;
}

/** 定时爬取倒计时 + 暂停/恢复 — 暂停时冻结剩余时间（类似 React 挂起）。 */
export function MonitorScheduleBar({
  task,
  pausing,
  resuming,
  onPause,
  onResume,
}: MonitorScheduleBarProps) {
  const countdown = useScheduleCountdown(task);

  if (!countdown.active) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-dashed border-border/80 bg-muted/20 px-4 py-3 text-[length:var(--text-sm)] text-muted-foreground">
        未启用定时爬取 — 仅可通过「立即运行」手动执行；可在配置 Tab 中开启定时。
      </div>
    );
  }

  const intervalSecs = Math.max(1, task.intervalMinutes) * 60;
  const progress = countdown.paused
    ? Math.round(((countdown.remainingSecs || 0) / intervalSecs) * 100)
    : Math.round(
        ((intervalSecs - Math.min(countdown.remainingSecs, intervalSecs)) / intervalSecs) * 100,
      );

  return (
    <div className="rounded-[var(--radius-lg)] border border-border/80 bg-card/80 px-4 py-3 backdrop-blur-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Clock className="size-4 shrink-0 text-primary" aria-hidden />
          <div className="min-w-0">
            <p className="text-[length:var(--text-sm)] font-medium text-foreground">
              {countdown.running
                ? "手动运行中 · 定时已重置并暂停"
                : countdown.paused
                  ? "定时已暂停"
                  : countdown.dueNow
                    ? "即将开始下一轮爬取"
                    : "距离下次爬取"}
            </p>
            <p className="font-mono text-[length:var(--text-lg)] font-semibold tabular-nums tracking-tight text-primary">
              {countdown.label}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {countdown.paused && !countdown.running ? (
            <AsyncButton size="sm" loading={resuming} onClick={onResume}>
              <Play className="mr-1.5 size-3.5" aria-hidden />
              恢复定时
            </AsyncButton>
          ) : !countdown.running ? (
            <Button size="sm" variant="outline" disabled={pausing} onClick={onPause}>
              <CirclePause className="mr-1.5 size-3.5" aria-hidden />
              暂停定时
            </Button>
          ) : null}
        </div>
      </div>
      <div className="mt-3 space-y-1">
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>
            每 {task.intervalMinutes} 分钟 ·{" "}
            {countdown.running
              ? "运行结束后需恢复定时"
              : countdown.paused
                ? "剩余时间已冻结"
                : "自动循环"}
          </span>
          {countdown.paused && task.scheduleRemainingSecs != null ? (
            <span>恢复后继续 {formatScheduleCountdown(task.scheduleRemainingSecs)}</span>
          ) : null}
        </div>
        <Progress value={Math.min(100, Math.max(0, progress))} />
      </div>
    </div>
  );
}
