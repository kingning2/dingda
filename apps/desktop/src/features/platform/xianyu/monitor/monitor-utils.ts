import { managePath } from "@desk/platform/compile";
import type { MonitorRun, MonitorTask } from "@desk/platform/ipc/xianyu-monitor";

export type MonitorFilter = "all" | "enabled" | "running" | "disabled";

export const FLOW_GRADIENTS = [
  "from-violet-600/50 via-fuchsia-500/25 to-emerald-600/20",
  "from-sky-600/50 via-indigo-500/25 to-violet-600/20",
  "from-amber-600/45 via-orange-500/20 to-rose-600/25",
  "from-emerald-600/45 via-teal-500/25 to-cyan-600/20",
  "from-rose-600/45 via-pink-500/20 to-violet-600/25",
] as const;

export function taskShortCode(taskId: string): string {
  const compact = taskId.replace(/-/g, "").slice(0, 6).toUpperCase();
  return compact || "TASK";
}

export function taskGradientIndex(taskId: string): number {
  let hash = 0;
  for (let i = 0; i < taskId.length; i += 1) {
    hash = (hash + taskId.charCodeAt(i) * (i + 1)) % FLOW_GRADIENTS.length;
  }
  return hash;
}

export interface TaskFlowHealth {
  percent: number;
  label: string;
  tone: "success" | "warning" | "danger" | "muted";
}

/** 从任务状态推导流程健康度（列表卡片用，不依赖运行记录）。 */
export function taskFlowHealth(task: MonitorTask): TaskFlowHealth {
  if (task.isRunning) {
    return { percent: 58, label: "流程执行中", tone: "warning" };
  }
  if (task.lastError) {
    return { percent: 24, label: "上次运行失败", tone: "danger" };
  }
  if (!task.enabled) {
    return { percent: 12, label: "已停用", tone: "muted" };
  }
  if (task.lastRunAt) {
    return { percent: 78, label: "流程正常", tone: "success" };
  }
  return { percent: 36, label: "等待首次运行", tone: "muted" };
}

export function taskStatusLabel(task: MonitorTask): string {
  if (task.isRunning) {
    return "运行中";
  }
  if (task.schedulePaused && task.enabled) {
    return "定时已暂停";
  }
  if (!task.enabled) {
    return "仅手动";
  }
  if (task.lastError) {
    return "异常";
  }
  return "启用";
}

export function formatMonitorTime(value?: string): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function filterMonitorTasks(tasks: MonitorTask[], filter: MonitorFilter): MonitorTask[] {
  switch (filter) {
    case "enabled":
      return tasks.filter((task) => task.enabled && !task.isRunning);
    case "running":
      return tasks.filter((task) => task.isRunning);
    case "disabled":
      return tasks.filter((task) => !task.enabled);
    default:
      return tasks;
  }
}

export function searchMonitorTasks(tasks: MonitorTask[], query: string): MonitorTask[] {
  const q = query.trim().toLowerCase();
  if (!q) {
    return tasks;
  }
  return tasks.filter((task) => {
    const haystack = [task.name, task.intent, task.aiCriteria, ...task.keywords].join(" ").toLowerCase();
    return haystack.includes(q);
  });
}

export function runSuccessRate(runs: MonitorRun[]): { closed: number; total: number; open: number } {
  const total = runs.length;
  const closed = runs.filter((run) => run.status === "success").length;
  const open = runs.filter((run) => run.status === "running" || run.status === "failed").length;
  return { closed, total, open };
}

/** 监控任务详情页路径。 */
export function monitorTaskDetailPath(taskId: string): string {
  return `${managePath("monitor")}/tasks/${encodeURIComponent(taskId)}`;
}

/** 从路径解析监控任务 ID（`/manage/.../monitor/tasks/:taskId`）。 */
export function monitorTaskIdFromPathname(pathname: string): string | null {
  const prefix = `${managePath("monitor")}/tasks/`;
  if (!pathname.startsWith(prefix)) {
    return null;
  }
  const segment = pathname.slice(prefix.length).split("/")[0] ?? "";
  return segment ? decodeURIComponent(segment) : null;
}
