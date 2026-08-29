/**
 * 任务中心 — 列出 AgentRun，发起 price_compare。
 */

import { useCallback, useEffect, useState } from "react";
import { Button, DataTable, Input, PageScaffold, type ColumnDef } from "@desk/ui";
import {
  SectionEmpty,
  TASK_TABLE_COLUMNS,
  type TaskRow,
} from "@components/product-shell";
import {
  agentRunList,
  agentRunStart,
  type AgentRunRecord,
} from "@desk/platform/ipc/agent-run";
import { useWorkspaceNav } from "../../app/use-workspace-tabs";
import {
  formatRunTime,
  kindLabel,
  progressLabel,
  stateLabel,
} from "./price-compare";

function mapRunToRow(run: AgentRunRecord): TaskRow {
  return {
    id: run.id,
    type: kindLabel(run.kind),
    status: stateLabel(run.state),
    progress: progressLabel(run),
    updatedAt: formatRunTime(run.updatedAt),
  };
}

/** 业务任务列表：投影 AgentRun。 */
export function TasksPage() {
  const { selectTab } = useWorkspaceNav();
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<TaskRow[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  const refresh = useCallback(async () => {
    setListError(null);
    try {
      const runs = await agentRunList();
      const sorted = [...runs].sort((a, b) => b.updatedAt - a.updatedAt);
      setRows(sorted.map(mapRunToRow));
    } catch (err: unknown) {
      setListError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const columns: ColumnDef<TaskRow, unknown>[] = [
    ...TASK_TABLE_COLUMNS,
    {
      id: "actions",
      header: "操作",
      cell: ({ row }) => (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => selectTab(`/tasks/${row.original.id}`)}
        >
          查看
        </Button>
      ),
    },
  ];

  async function handleStart() {
    const user = query.trim();
    if (!user || starting) {
      return;
    }
    setStarting(true);
    setListError(null);
    try {
      const run = await agentRunStart({ user });
      selectTab(`/tasks/${run.id}`);
    } catch (err: unknown) {
      setListError(err instanceof Error ? err.message : String(err));
      setStarting(false);
    }
  }

  return (
    <PageScaffold
      title="任务中心"
      subtitle="选品比价 AgentRun（price_compare）"
      ambient="none"
      containerPadding="sm"
      extra={
        <div className="flex items-center gap-2">
          <Button type="button" size="sm" variant="outline" onClick={() => selectTab("/tasks/copilot")}>
            AI 副驾
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => void refresh()}>
            刷新
          </Button>
        </div>
      }
    >
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="输入选品查询，例如：便携榨汁杯 利润结构"
          className="flex-1"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void handleStart();
            }
          }}
        />
        <Button
          type="button"
          size="sm"
          disabled={!query.trim() || starting}
          onClick={() => void handleStart()}
        >
          {starting ? "启动中…" : "开始比价"}
        </Button>
      </div>

      {listError ? (
        <p className="mb-3 text-[length:var(--text-sm)] text-destructive">{listError}</p>
      ) : null}

      {loading ? (
        <p className="py-8 text-center text-[length:var(--text-sm)] text-muted-foreground">
          加载中…
        </p>
      ) : (
        <DataTable<TaskRow>
          columns={columns}
          data={rows}
          getRowId={(row) => row.id}
          emptyText="暂无任务，输入查询后点「开始比价」"
        />
      )}

      <SectionEmpty
        title="说明"
        description="需在设置中配置 AI 账号；渠道采集需设置 → 账号中已登录闲鱼账号（有效 Cookie）。"
      />
    </PageScaffold>
  );
}
