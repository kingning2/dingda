/**
 * 闲鱼订单管理页（迁移自原前端 `pages/orders/Orders.tsx`）。
 *
 * 按原前端核心交互重写：订单列表 + 状态筛选 + 关键词搜索 + 状态/发货信息更新 + 删除。
 * 数据访问走 Tauri IPC（`@desk/platform/ipc/order`），复用 crates/app OrderService。
 */

import { ORDER_STATUS_LABELS as STATUS_LABEL } from "@components/order-status";
import { OWNER_ID } from "@desk/platform/constants";
import { useEffect, useMemo, useState } from "react";
import {
  Button,
  ConfirmModal,
  Input,
  Loading,
  PageScaffold,
  Pagination,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  toast,
} from "@desk/ui";
import { Trash2 } from "@desk/ui/icons";
import {
  orderDelete,
  orderList,
  orderUpdateStatus,
  type Order,
  type OrderStatus,
} from "@desk/platform/ipc/order";
import { formatAmount, getErrorMessage } from "@desk/utils";

const PAGE_SIZE = 20;

const STATUS_OPTIONS: { value: OrderStatus | "all"; label: string }[] = [
  { value: "all", label: "全部状态" },
  { value: "pending", label: "待付款" },
  { value: "paid", label: "待发货" },
  { value: "shipped", label: "已发货" },
  { value: "completed", label: "已完成" },
  { value: "closed", label: "已关闭" },
  { value: "refunded", label: "已退款" },
];


/**
 * 闲鱼订单管理页。
 *
 * @author agent
 * @created 2026-08-13
 */
export function XianyuOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<OrderStatus | "all">("all");
  const [keyword, setKeyword] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Order | null>(null);

  async function load(nextPage = page, nextStatus = statusFilter, nextKeyword = keyword) {
    setLoading(true);
    try {
      const [list, count] = await orderList({
        owner_id: OWNER_ID,
        page: nextPage,
        page_size: PAGE_SIZE,
        status: nextStatus === "all" ? undefined : nextStatus,
        keyword: nextKeyword.trim() || undefined,
      });
      setOrders(list);
      setTotal(count);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void orderList({
      owner_id: OWNER_ID,
      page: 1,
      page_size: PAGE_SIZE,
      status: statusFilter === "all" ? undefined : statusFilter,
      keyword: keyword.trim() || undefined,
    })
      .then(([list, count]) => {
        if (cancelled) return;
        setOrders(list);
        setTotal(count);
        setPage(1);
      })
      .catch((error) => {
        if (!cancelled) {
          toast.error(getErrorMessage(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  async function handleSearch() {
    await load(1, statusFilter, keyword);
  }

  async function handleStatusChange(order: Order, status: OrderStatus) {
    try {
      await orderUpdateStatus(order.order_no, status);
      toast.success("订单状态已更新");
      await load();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await orderDelete(OWNER_ID, deleteTarget.id);
      toast.success("订单已删除");
      setDeleteTarget(null);
      await load();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  return (
    <PageScaffold subtitle="查看订单、按状态筛选，并更新发货与售后进度">
      <div className="space-y-4">
        {/* 工具栏 */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Input
              placeholder="搜索订单号、商品或买家"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleSearch();
              }}
              className="w-64"
            />
            <Button variant="outline" size="sm" onClick={() => void handleSearch()}>
              搜索
            </Button>
            <Select
              value={statusFilter}
              onValueChange={(value) => setStatusFilter(value as OrderStatus | "all")}
            >
              <SelectTrigger className="w-32">
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <span className="text-[length:var(--text-sm)] text-muted-foreground">
            共 {total} 笔订单
          </span>
        </div>

        {/* 列表 */}
        {loading ? (
          <Loading size="lg" text="加载中..." className="py-16" />
        ) : orders.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground">暂无订单</div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full text-[length:var(--text-sm)]">
              <thead className="bg-muted/50 text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium">订单号</th>
                  <th className="px-4 py-2.5 text-left font-medium">商品</th>
                  <th className="px-4 py-2.5 text-left font-medium">买家</th>
                  <th className="px-4 py-2.5 text-left font-medium">金额</th>
                  <th className="px-4 py-2.5 text-left font-medium">状态</th>
                  <th className="px-4 py-2.5 text-left font-medium">评价</th>
                  <th className="px-4 py-2.5 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {orders.map((order) => (
                  <tr key={order.id} className="hover:bg-muted/30">
                    <td className="px-4 py-2.5 font-mono">{order.order_no}</td>
                    <td className="px-4 py-2.5">
                      <p className="max-w-56 truncate">{order.item_title || "—"}</p>
                      <p className="font-mono text-[length:var(--text-xs)] text-muted-foreground">
                        {order.item_id}
                      </p>
                    </td>
                    <td className="px-4 py-2.5 font-mono">{order.buyer_id || "—"}</td>
                    <td className="px-4 py-2.5">{formatAmount(order.amount)} 元</td>
                    <td className="px-4 py-2.5">
                      <Select
                        value={order.status}
                        onValueChange={(value) => void handleStatusChange(order, value as OrderStatus)}
                      >
                        <SelectTrigger className="h-7 w-24">
                          <SelectValue>{STATUS_LABEL[order.status] ?? order.status}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          {STATUS_OPTIONS.filter((option) => option.value !== "all").map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={
                          order.is_rated
                            ? "rounded-full bg-emerald-500/15 px-2 py-0.5 text-[length:var(--text-xs)] text-emerald-500"
                            : "rounded-full bg-muted px-2 py-0.5 text-[length:var(--text-xs)] text-muted-foreground"
                        }
                      >
                        {order.is_rated ? "已评价" : "未评价"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-destructive"
                        onClick={() => setDeleteTarget(order)}
                      >
                        <Trash2 className="size-3.5" aria-hidden />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 分页 */}
        <Pagination page={page} totalPages={totalPages} onPageChange={(next) => void load(next)} />
      </div>

      {/* 删除确认 */}
      <ConfirmModal
        isOpen={deleteTarget !== null}
        type="danger"
        title="删除订单"
        message={`确认删除订单「${deleteTarget?.order_no ?? ""}」？`}
        confirmText="删除"
        onConfirm={() => void handleDelete()}
        onCancel={() => setDeleteTarget(null)}
      />
    </PageScaffold>
  );
}
