/**
 * 监控列表：一条监控目标一行。
 *
 * 职责：
 *     渲染监控目标列表与空态；选中项高亮，点击交给上层切换右侧详情。
 *
 * 设计说明：
 *     标题为空时回落到 `item_id`：目标刚加入、首次轮询还没跑完时后端只有 id，
 *     这时候列表不能是空白条 —— 用户会以为没加上。
 */

import type { MonitorTargetItem } from "@v2/contracts/monitor";
import { Badge } from "@v2/ui-primitives/badge";
import { Card, CardContent } from "@v2/ui-primitives/card";
import { cn } from "@v2/ui-primitives/utils";
import { Loader2 } from "lucide-react";

import { formatDrop, formatPrice, soldStateView } from "./monitor-format";
import { platformLabel } from "./monitor-platforms";

interface MonitorListProps {
  targets: MonitorTargetItem[];
  selectedId: string | null;
  loading: boolean;
  onSelect: (targetId: string) => void;
}

/** 监控目标列表。 */
export function MonitorList({ targets, selectedId, loading, onSelect }: MonitorListProps) {
  if (loading && targets.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
        <Loader2 className="size-6 animate-spin" />
        <p className="text-sm">正在读取监控列表…</p>
      </div>
    );
  }

  if (targets.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          还没有监控中的商品。点「加入监控」填平台与商品 ID，或到 Agent 选品结果里一键加入。
        </p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {targets.map((target) => {
        const state = soldStateView(target.sold_state);
        const active = target.target_id === selectedId;
        const meta = [
          platformLabel(target.platform),
          target.last_want_count ? `想要 ${target.last_want_count}` : null,
          target.last_poll_at ? null : "尚未轮询",
        ].filter(Boolean);

        return (
          <li key={target.target_id}>
            <Card
              size="sm"
              role="button"
              tabIndex={0}
              aria-pressed={active}
              className={cn(
                "cursor-pointer transition",
                active ? "ring-primary/60" : "ring-border/70 hover:ring-primary/40",
              )}
              onClick={() => onSelect(target.target_id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(target.target_id);
                }
              }}
            >
              <CardContent className="flex flex-col gap-1.5">
                <div className="flex items-start justify-between gap-2">
                  <p className="line-clamp-2 min-w-0 flex-1 text-sm leading-snug font-medium">
                    {target.title || target.item_id}
                  </p>
                  <Badge
                    className={cn("h-auto shrink-0 rounded-full border-transparent", state.className)}
                  >
                    {state.label}
                  </Badge>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-base font-semibold text-foreground">
                    {formatPrice(target.last_price)}
                  </span>
                  <span className="text-xs text-muted-foreground">{formatDrop(target)}</span>
                </div>
                <p className="truncate text-xs text-muted-foreground">{meta.join(" · ")}</p>
              </CardContent>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
