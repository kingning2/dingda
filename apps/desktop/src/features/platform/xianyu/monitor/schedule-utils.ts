import { useEffect, useMemo, useState } from "react";
import type { MonitorTask } from "@desk/platform/ipc/xianyu-monitor";

export function formatScheduleCountdown(totalSecs: number): string {
  const secs = Math.max(0, Math.floor(totalSecs));
  const hours = Math.floor(secs / 3600);
  const minutes = Math.floor((secs % 3600) / 60);
  const seconds = secs % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function remainingSecsFromTask(task: MonitorTask, nowMs: number): number {
  if (task.schedulePaused) {
    return task.scheduleRemainingSecs ?? 0;
  }
  if (task.nextRunAt) {
    const target = new Date(task.nextRunAt).getTime();
    if (!Number.isNaN(target)) {
      return Math.max(0, Math.ceil((target - nowMs) / 1000));
    }
  }
  if (task.lastRunAt) {
    const last = new Date(task.lastRunAt).getTime();
    if (!Number.isNaN(last)) {
      const intervalMs = Math.max(1, task.intervalMinutes) * 60_000;
      return Math.max(0, Math.ceil((last + intervalMs - nowMs) / 1000));
    }
  }
  return 0;
}

export type ScheduleCountdownState =
  | { active: false }
  | {
      active: true;
      paused: boolean;
      /** 手动/调度运行中 — 定时器已重置并暂停。 */
      running?: boolean;
      remainingSecs: number;
      label: string;
      dueNow: boolean;
    };

/** 定时爬取倒计时 — 暂停时显示冻结剩余时间。 */
export function useScheduleCountdown(task: MonitorTask | null): ScheduleCountdownState {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!task?.enabled || task.isRunning) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [task?.enabled, task?.isRunning, task?.schedulePaused, task?.nextRunAt, task?.scheduleRemainingSecs]);

  return useMemo(() => {
    if (!task?.enabled) {
      return { active: false };
    }
    if (task.isRunning) {
      const fullSecs = Math.max(1, task.intervalMinutes) * 60;
      return {
        active: true,
        paused: true,
        running: true,
        remainingSecs: task.scheduleRemainingSecs ?? fullSecs,
        label: formatScheduleCountdown(task.scheduleRemainingSecs ?? fullSecs),
        dueNow: false,
      };
    }
    const remainingSecs = remainingSecsFromTask(task, now);
    return {
      active: true,
      paused: Boolean(task.schedulePaused),
      running: false,
      remainingSecs,
      label: formatScheduleCountdown(remainingSecs),
      dueNow: !task.schedulePaused && remainingSecs <= 0,
    };
  }, [task, now]);
}
