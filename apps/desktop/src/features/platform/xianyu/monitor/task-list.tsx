import { SpotlightCard } from "@desk/ui";
import type { MonitorTask } from "@desk/platform/ipc/xianyu-monitor";

export interface TaskListProps {
  tasks: MonitorTask[];
  selectedId: string;
  loading: boolean;
  onSelect: (task: MonitorTask) => void;
  onNew: () => void;
}

/** 监控任务列表（左栏）。 */
export function TaskList({ tasks, selectedId, loading, onSelect, onNew }: TaskListProps) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">监控任务</h2>
        <button
          type="button"
          onClick={onNew}
          className="rounded-md border border-border bg-background px-2.5 py-1 text-xs font-medium transition-colors hover:bg-muted/50"
        >
          新建
        </button>
      </div>
      <ul className="space-y-2">
        {tasks.map((task) => {
          const selected = selectedId === task.id;
          return (
            <li key={task.id}>
              <SpotlightCard lift={false}>
                <button
                  type="button"
                  onClick={() => onSelect(task)}
                  className={`relative w-full rounded-[var(--radius-lg)] border px-3 py-2 text-left text-sm transition-colors ${
                    selected
                      ? "border-primary/50 bg-primary/10"
                      : "border-border/70 bg-card hover:bg-muted/40"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{task.name}</span>
                    {task.isRunning ? (
                      <span className="text-xs text-primary">运行中</span>
                    ) : task.enabled ? (
                      <span className="text-xs text-muted-foreground">启用</span>
                    ) : (
                      <span className="text-xs text-muted-foreground">停用</span>
                    )}
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{task.intent}</p>
                </button>
              </SpotlightCard>
            </li>
          );
        })}
      </ul>
      {!loading && tasks.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无监控任务，右侧创建第一个。</p>
      ) : null}
    </section>
  );
}
