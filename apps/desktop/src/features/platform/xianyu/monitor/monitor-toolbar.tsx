import { Button, Input, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@desk/ui";
import { Filter, Plus } from "@desk/ui/icons";
import type { MonitorFilter } from "./monitor-utils";

export interface MonitorToolbarProps {
  taskCount: number;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  filter: MonitorFilter;
  onFilterChange: (value: MonitorFilter) => void;
  onCreate: () => void;
}

/** 监控任务列表工具栏 — 参考 project-list-1。 */
export function MonitorToolbar({
  taskCount,
  searchQuery,
  onSearchChange,
  filter,
  onFilterChange,
  onCreate,
}: MonitorToolbarProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 className="text-[length:var(--text-sm)] font-semibold text-foreground">监控任务</h2>
        <p className="text-[length:var(--text-xs)] text-muted-foreground">{taskCount} 个任务</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="搜索任务…"
          className="h-8 w-full min-w-[12rem] sm:w-48"
        />
        <Select value={filter} onValueChange={(value) => onFilterChange(value as MonitorFilter)}>
          <SelectTrigger className="h-8 w-[7.5rem]">
            <Filter className="mr-1.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部</SelectItem>
            <SelectItem value="enabled">已启用</SelectItem>
            <SelectItem value="running">运行中</SelectItem>
            <SelectItem value="disabled">已停用</SelectItem>
          </SelectContent>
        </Select>
        <Button size="sm" onClick={onCreate}>
          <Plus className="size-3.5" aria-hidden />
          新建监控
        </Button>
      </div>
    </div>
  );
}
