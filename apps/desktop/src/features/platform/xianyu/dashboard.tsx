/**
 * 闲鱼仪表盘页 — Bento 布局 + Aceternity KPI 卡片 + 快捷入口。
 *
 * 数据访问走 Tauri IPC（`@desk/platform/ipc/dashboard`）。
 */

import { OWNER_ID } from "@desk/platform/constants";
import { useEffect, useState } from "react";
import {
  Activity,
  ChevronRight,
  Package,
  Search,
  ShoppingCart,
  Users,
  type LucideIcon,
} from "@desk/ui/icons";
import {
  AnimatedStatCard,
  BentoCard,
  BentoGrid,
  Loading,
  PageScaffold,
} from "@desk/ui";
import { dashboardStats, type DashboardStats } from "@desk/platform/ipc/dashboard";
import { managePath } from "@desk/platform/compile";
import { useWorkspaceNav } from "../../../app/use-workspace-tabs";

interface StatCardDef {
  key: keyof DashboardStats;
  icon: LucideIcon;
  label: string;
  color: string;
  manageKey: string;
  hint?: string;
}

const STAT_CARDS: StatCardDef[] = [
  {
    key: "total_accounts",
    icon: Users,
    label: "总账号数",
    color: "text-blue-500",
    manageKey: "accounts",
  },
  {
    key: "active_accounts",
    icon: Activity,
    label: "启用账号",
    color: "text-amber-500",
    manageKey: "accounts",
    hint: "可用于自动化任务",
  },
  {
    key: "total_items",
    icon: Package,
    label: "商品数",
    color: "text-violet-500",
    manageKey: "items",
  },
  {
    key: "total_orders",
    icon: ShoppingCart,
    label: "总订单",
    color: "text-blue-500",
    manageKey: "orders",
  },
  {
    key: "pending_ship_orders",
    icon: ShoppingCart,
    label: "待发货",
    color: "text-amber-500",
    manageKey: "orders",
    hint: "需尽快处理",
  },
];

interface QuickAction {
  label: string;
  description: string;
  manageKey: string;
  icon: LucideIcon;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    label: "账号管理",
    description: "绑定与启用闲鱼账号",
    manageKey: "accounts",
    icon: Users,
  },
  {
    label: "商品搜索",
    description: "关键词检索闲鱼商品",
    manageKey: "search",
    icon: Search,
  },
  {
    label: "商品管理",
    description: "上架与库存维护",
    manageKey: "items",
    icon: Package,
  },
  {
    label: "订单管理",
    description: "发货与售后处理",
    manageKey: "orders",
    icon: ShoppingCart,
  },
];

/** 闲鱼仪表盘页。 */
export function XianyuDashboardPage() {
  const { selectTab } = useWorkspaceNav();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void dashboardStats(OWNER_ID)
      .then((data) => {
        if (!cancelled) {
          setStats(data);
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
  }, []);

  function goManage(key: string) {
    selectTab(managePath(key));
  }

  return (
    <PageScaffold title="仪表盘" subtitle="闲鱼账号自动化运营概览">
      <section className="space-y-1">
        <p className="text-[length:var(--text-sm)] text-muted-foreground">
          欢迎回来 — 以下是当前运营快照与常用入口。
        </p>
      </section>

      {loading ? (
        <Loading size="lg" text="加载中..." className="py-20" />
      ) : stats ? (
        <div className="space-y-6">
          <BentoGrid columns={5}>
            {STAT_CARDS.map((card) => (
              <AnimatedStatCard
                key={card.key}
                label={card.label}
                value={stats[card.key]}
                icon={card.icon}
                iconClassName={card.color}
                hint={card.hint}
                onAction={() => goManage(card.manageKey)}
              />
            ))}
          </BentoGrid>

          <BentoGrid columns={3} className="lg:grid-cols-3">
            <BentoCard colSpan={2} glow className="min-h-[220px]">
              <h2 className="text-[length:var(--text-sm)] font-medium text-foreground">
                数据趋势
              </h2>
              <p className="mt-2 text-[length:var(--text-sm)] text-muted-foreground">
                订单与商品趋势图将在后续版本接入。当前可通过下方快捷入口进入各管理页查看明细。
              </p>
              <div className="mt-6 flex h-28 items-end gap-2">
                {[42, 68, 55, 82, 64, 90, 72].map((height, index) => (
                  <div
                    key={index}
                    className="flex-1 rounded-t-md bg-primary/20 transition-colors hover:bg-primary/35"
                    style={{ height: `${height}%` }}
                    aria-hidden
                  />
                ))}
              </div>
            </BentoCard>

            <BentoCard glow className="min-h-[220px]">
              <h2 className="text-[length:var(--text-sm)] font-medium text-foreground">
                运营快照
              </h2>
              <ul className="mt-4 space-y-3 text-[length:var(--text-sm)]">
                <li className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground">账号启用率</span>
                  <span className="font-medium tabular-nums text-foreground">
                    {stats.total_accounts > 0
                      ? `${Math.round((stats.active_accounts / stats.total_accounts) * 100)}%`
                      : "—"}
                  </span>
                </li>
                <li className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground">待发货占比</span>
                  <span className="font-medium tabular-nums text-foreground">
                    {stats.total_orders > 0
                      ? `${Math.round((stats.pending_ship_orders / stats.total_orders) * 100)}%`
                      : "—"}
                  </span>
                </li>
                <li className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground">人均商品</span>
                  <span className="font-medium tabular-nums text-foreground">
                    {stats.active_accounts > 0
                      ? Math.round(stats.total_items / stats.active_accounts)
                      : "—"}
                  </span>
                </li>
              </ul>
            </BentoCard>
          </BentoGrid>

          <BentoCard glow>
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-[length:var(--text-sm)] font-medium text-foreground">
                快捷操作
              </h2>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {QUICK_ACTIONS.map((action) => {
                const Icon = action.icon;
                return (
                  <button
                    key={action.manageKey}
                    type="button"
                    onClick={() => goManage(action.manageKey)}
                    className="group flex items-start gap-3 rounded-[var(--radius-lg)] border border-border/60 bg-background/40 p-3 text-left transition-colors hover:border-primary/30 hover:bg-muted/30"
                  >
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-muted/80">
                      <Icon className="size-4 text-primary" aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1 text-[length:var(--text-sm)] font-medium text-foreground">
                        {action.label}
                        <ChevronRight
                          className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100"
                          aria-hidden
                        />
                      </span>
                      <span className="mt-0.5 block text-[length:var(--text-xs)] text-muted-foreground">
                        {action.description}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </BentoCard>
        </div>
      ) : null}
    </PageScaffold>
  );
}
