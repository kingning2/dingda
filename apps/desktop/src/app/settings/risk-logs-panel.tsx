/**
 * 设置弹窗 — 风控日志查询与清理。
 *
 * 数据访问走 Tauri IPC（`@desk/platform/ipc/risk`）。
 */

import { OWNER_ID } from "@desk/platform/constants";
import { useEffect, useState } from "react";
import {
  Button,
  ConfirmModal,
  Input,
  Loading,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  toast,
} from "@desk/ui";
import { Calendar, RefreshCw, ShieldAlert, Trash2 } from "@desk/ui/icons";
import { accountList, type XianyuAccount } from "@desk/platform/ipc/account";
import {
  riskLogClear,
  riskLogClearProcessing,
  riskLogList,
  type RiskLogItem,
} from "@desk/platform/ipc/risk";

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

const STATUS_LABELS: Record<string, string> = {
  success: "成功",
  failed: "失败",
  processing: "处理中",
  cancelled: "已取消",
};

interface Filters {
  accountId: string;
  startDate: string;
  endDate: string;
  status: string;
}

const EMPTY_FILTERS: Filters = {
  accountId: "",
  startDate: "",
  endDate: "",
  status: "",
};

/** 风控日志设置面板。 */
export function RiskLogsPanel() {
  const [logs, setLogs] = useState<RiskLogItem[]>([]);
  const [accounts, setAccounts] = useState<XianyuAccount[]>([]);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [clearConfirm, setClearConfirm] = useState(false);
  const [clearProcessingConfirm, setClearProcessingConfirm] = useState(false);
  const [clearing, setClearing] = useState(false);

  async function load(nextPage = page, nextPageSize = pageSize) {
    setLoading(true);
    try {
      const result = await riskLogList({
        page: nextPage,
        page_size: nextPageSize,
        account_id: filters.accountId || undefined,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
        processing_status: filters.status || undefined,
      });
      setLogs(result.data);
      setPage(result.page);
      setPageSize(result.page_size);
      setTotal(result.total);
      setTotalPages(result.total_pages);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void accountList(OWNER_ID)
      .then((list) => {
        if (!cancelled) setAccounts(list);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void load(1, 20).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const patchFilters = (patch: Partial<Filters>) =>
    setFilters((current) => ({ ...current, ...patch }));

  function statusLabel(log: RiskLogItem): string {
    return STATUS_LABELS[log.processing_status] ?? (log.processing_status || "-");
  }

  function accountLabel(accountId: string): string {
    const account = accounts.find((item) => item.account_id === accountId);
    if (account?.display_name) {
      return `${account.display_name} (${accountId})`;
    }
    return accountId;
  }

  async function handleClear() {
    setClearing(true);
    try {
      await riskLogClear();
      toast.success("日志已清空");
      setClearConfirm(false);
      await load(1);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setClearing(false);
    }
  }

  async function handleClearProcessing() {
    setClearing(true);
    try {
      await riskLogClearProcessing();
      toast.success("处理中日志已清空");
      setClearProcessingConfirm(false);
      await load(1);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setClearing(false);
    }
  }

  return (
    <>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="block space-y-1">
            <span className="text-[length:var(--text-xs)] text-muted-foreground">开始日期</span>
            <Input
              type="date"
              value={filters.startDate}
              onChange={(event) => patchFilters({ startDate: event.target.value })}
              className="w-36"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-[length:var(--text-xs)] text-muted-foreground">结束日期</span>
            <Input
              type="date"
              value={filters.endDate}
              onChange={(event) => patchFilters({ endDate: event.target.value })}
              className="w-36"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-[length:var(--text-xs)] text-muted-foreground">处理状态</span>
            <Select value={filters.status} onValueChange={(value) => patchFilters({ status: value })}>
              <SelectTrigger className="w-28" aria-label="处理状态">
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">全部状态</SelectItem>
                <SelectItem value="success">成功</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
                <SelectItem value="processing">处理中</SelectItem>
                <SelectItem value="cancelled">已取消</SelectItem>
              </SelectContent>
            </Select>
          </label>
          <label className="block space-y-1">
            <span className="text-[length:var(--text-xs)] text-muted-foreground">筛选账号</span>
            <Select
              value={filters.accountId}
              onValueChange={(value) => patchFilters({ accountId: value })}
            >
              <SelectTrigger className="w-40" aria-label="筛选账号">
                <SelectValue placeholder="全部账号" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">全部账号</SelectItem>
                {accounts.map((account) => (
                  <SelectItem key={account.account_id} value={account.account_id}>
                    {account.display_name
                      ? `${account.display_name} (${account.account_id})`
                      : account.account_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          <Button size="sm" onClick={() => void load(1)}>
            <Calendar className="size-4" aria-hidden />
            查询
          </Button>
        </div>

        <div className="overflow-hidden rounded-xl border border-border">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/30 px-4 py-2">
            <div className="flex items-center gap-2">
              <span className="text-[length:var(--text-sm)] font-medium">日志列表</span>
              <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[length:var(--text-xs)] text-primary">
                {total} 条
              </span>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => void load(page)}>
                <RefreshCw className="size-4" aria-hidden />
                刷新
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-destructive"
                onClick={() => setClearProcessingConfirm(true)}
              >
                <Trash2 className="size-4" aria-hidden />
                清空处理中
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-destructive"
                onClick={() => setClearConfirm(true)}
              >
                <Trash2 className="size-4" aria-hidden />
                清空日志
              </Button>
            </div>
          </div>

          {loading ? (
            <Loading size="lg" text="加载中..." className="flex min-h-48 items-center justify-center" />
          ) : logs.length === 0 ? (
            <div className="flex min-h-48 flex-col items-center justify-center text-muted-foreground">
              <ShieldAlert className="mb-2 size-10 opacity-40" aria-hidden />
              暂无风控日志
            </div>
          ) : (
            <div className="max-h-[min(420px,50vh)] overflow-auto">
              <table className="w-max min-w-full text-[length:var(--text-xs)]">
                <thead className="sticky top-0 z-10 bg-muted/95 text-muted-foreground backdrop-blur-sm">
                  <tr>
                    <th className="whitespace-nowrap px-3 py-2 text-left font-medium">账号ID</th>
                    <th className="whitespace-nowrap px-3 py-2 text-left font-medium">事件描述</th>
                    <th className="whitespace-nowrap px-3 py-2 text-left font-medium">处理结果</th>
                    <th className="whitespace-nowrap px-3 py-2 text-left font-medium">失败原因</th>
                    <th className="whitespace-nowrap px-3 py-2 text-left font-medium">处理状态</th>
                    <th className="whitespace-nowrap px-3 py-2 text-left font-medium">创建时间</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-muted/30">
                      <td className="whitespace-nowrap px-3 py-2 align-top font-medium text-primary">
                        {accountLabel(log.account_id)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 align-top text-muted-foreground">
                        {log.message || "-"}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 align-top text-muted-foreground">
                        {log.processing_result || "-"}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 align-top text-destructive">
                        {log.error_message || "-"}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 align-top">
                        <StatusBadge status={log.processing_status} label={statusLabel(log)} />
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 align-top text-muted-foreground">
                        {log.created_at ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {total > 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-[length:var(--text-sm)] text-muted-foreground">
              <span>每页</span>
              <Select value={String(pageSize)} onValueChange={(value) => void load(1, Number(value))}>
                <SelectTrigger className="w-20" aria-label="每页条数">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAGE_SIZE_OPTIONS.map((size) => (
                    <SelectItem key={size} value={String(size)}>
                      {size}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span>条，共 {total} 条</span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => void load(Math.max(1, page - 1))}
              >
                上一页
              </Button>
              <span className="text-[length:var(--text-sm)] text-muted-foreground">
                第 {page} / {Math.max(1, totalPages)} 页
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= totalPages}
                onClick={() => void load(Math.min(totalPages, page + 1))}
              >
                下一页
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      <ConfirmModal
        isOpen={clearConfirm}
        type="danger"
        title="清空确认"
        message="确定要清空所有风控日志吗？此操作不可恢复！"
        confirmText="清空"
        loading={clearing}
        onConfirm={() => void handleClear()}
        onCancel={() => setClearConfirm(false)}
      />

      <ConfirmModal
        isOpen={clearProcessingConfirm}
        type="danger"
        title="清空处理中日志确认"
        message="确定要清空所有处理中状态的风控日志吗？此操作不可恢复！"
        confirmText="清空"
        loading={clearing}
        onConfirm={() => void handleClearProcessing()}
        onCancel={() => setClearProcessingConfirm(false)}
      />
    </>
  );
}

function StatusBadge({ status, label }: { status: string; label: string }) {
  const color =
    status === "success"
      ? "bg-emerald-500/15 text-emerald-600"
      : status === "failed"
        ? "bg-red-500/15 text-red-600"
        : status === "processing"
          ? "bg-amber-500/15 text-amber-600"
          : "bg-muted text-muted-foreground";
  return (
    <span className={`rounded-full px-2 py-0.5 text-[length:var(--text-xs)] ${color}`}>{label}</span>
  );
}
