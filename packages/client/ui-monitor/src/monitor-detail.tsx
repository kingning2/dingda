/**
 * 监控详情：当前快照 + 变更记录 + 价格历史。
 *
 * 职责：
 *     渲染单个监控目标的全量观测数据，并提供暂停/恢复与移除操作。
 *
 * 设计说明：
 *     - 变更记录与价格历史都**倒序展示**（最新在前）：用户打开详情先想知道「最近怎么样了」，
 *       正序会让他每次都要滚到底。后端给的是正序，反转在前端做，不改线协议。
 *     - 列表用 `observed_at` 作 key。同一时刻不会有两个点（后端一次轮询只落一个点），
 *       所以不需要拼 kind 之外的复合 key。
 *     - 这里不画折线图：价格点数量少、横轴时间不等距，折线会误导。
 *       等点够密（比如一周后）再考虑加。
 */

import type { MonitorDetailResponse, MonitorPatchRequest } from "@v2/contracts/monitor";
import { Badge } from "@v2/ui-primitives/badge";
import { Button } from "@v2/ui-primitives/button";
import { Card, CardContent } from "@v2/ui-primitives/card";
import { cn } from "@v2/ui-primitives/utils";
import { Loader2 } from "lucide-react";

import {
  changeKindView,
  formatDrop,
  formatInterval,
  formatPrice,
  formatRelativeTime,
  monitorStateLabel,
  soldStateView,
} from "./monitor-format";
import { platformLabel } from "./monitor-platforms";

interface MonitorDetailProps {
  detail: MonitorDetailResponse | null;
  loading: boolean;
  /** 渲染基准时间；由上层传入，保证同一屏内的相对时间一致。 */
  now: number;
  onPatch: (targetId: string, request: MonitorPatchRequest) => void;
  onRemove: (targetId: string) => void;
}

/** 单条监控的详情面板。 */
export function MonitorDetail({ detail, loading, now, onPatch, onRemove }: MonitorDetailProps) {
  if (!detail && loading) {
    return (
      <Card className="ring-border/70">
        <CardContent className="flex items-center justify-center gap-3 py-16 text-muted-foreground">
          <Loader2 className="size-5 animate-spin" />
          <span className="text-sm">正在读取监控详情…</span>
        </CardContent>
      </Card>
    );
  }

  if (!detail) {
    return (
      <Card className="border-dashed ring-0">
        <CardContent className="py-16 text-center text-sm text-muted-foreground">
          从左侧选一条监控，这里会显示它的价格历史与变更记录。
        </CardContent>
      </Card>
    );
  }

  const { target, points, changes } = detail;
  const state = soldStateView(target.sold_state);
  const paused = target.state === "paused";
  const lastPoll = target.last_poll_at ? formatRelativeTime(target.last_poll_at, now) : "尚未轮询";

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="line-clamp-2 text-base leading-snug font-semibold">
              {target.title || target.item_id}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {platformLabel(target.platform)} · {monitorStateLabel(target.state)} · 每{" "}
              {formatInterval(target.poll_interval_seconds)} 轮询 · 上次 {lastPoll}
            </p>
          </div>
          <Badge className={cn("h-auto shrink-0 rounded-full border-transparent", state.className)}>
            {state.label}
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              onPatch(target.target_id, { state: paused ? "active" : "paused" })
            }
          >
            {paused ? "恢复监控" : "暂停监控"}
          </Button>
          <Button size="sm" variant="outline" onClick={() => onRemove(target.target_id)}>
            移除
          </Button>
          {target.url ? (
            <a
              href={target.url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-primary hover:underline"
            >
              打开商品页 ↗
            </a>
          ) : null}
        </div>

        {target.last_error ? (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            最近一次轮询失败：{target.last_error}（连续失败 {target.fail_count} 次）
          </p>
        ) : null}
      </header>

      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat label="首价" value={formatPrice(target.first_price)} />
        <Stat label="现价" value={formatPrice(target.last_price)} />
        <Stat label="涨跌" value={formatDrop(target)} />
        <Stat label="最低" value={formatPrice(target.min_price)} />
        <Stat label="最高" value={formatPrice(target.max_price)} />
        <Stat label="已监控" value={formatDuration(target.watched_hours)} />
      </dl>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-foreground">变更记录</h3>
        {changes.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            还没有值得记录的变更。降价、售出、下架会在后续轮询中出现在这里。
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {changes
              .slice()
              .reverse()
              .map((change) => {
                const view = changeKindView(change.kind);
                return (
                  <li
                    key={change.observed_at}
                    className="flex items-start gap-2 text-xs text-foreground"
                  >
                    <Badge
                      className={cn(
                        "h-auto shrink-0 rounded-full border-transparent",
                        view.className,
                      )}
                    >
                      {view.label}
                    </Badge>
                    <span className="min-w-0 flex-1">{change.message}</span>
                    <span className="shrink-0 text-muted-foreground">
                      {formatRelativeTime(change.observed_at, now)}
                    </span>
                  </li>
                );
              })}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-foreground">价格历史（{points.length} 个点）</h3>
        {points.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            还没有观测点。后台调度器每分钟检查一次到期目标，加入后通常 1 分钟内会出现第一条。
          </p>
        ) : (
          <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto pr-1">
            {points
              .slice()
              .reverse()
              .map((point) => (
                <li
                  key={point.observed_at}
                  className="flex items-center gap-2 rounded-md px-2 py-1 text-xs odd:bg-muted/30"
                >
                  <span className="w-20 shrink-0 text-muted-foreground">
                    {formatRelativeTime(point.observed_at, now)}
                  </span>
                  <span className="min-w-0 flex-1 font-medium">
                    {point.price_text?.trim() || formatPrice(point.price)}
                  </span>
                  <span className="shrink-0 text-muted-foreground">
                    {soldStateView(point.sold_state).label}
                  </span>
                </li>
              ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** 单个快照指标。 */
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-foreground">{value}</dd>
    </div>
  );
}

/** 已监控小时数 → 展示串。不足一天按小时给，超过按天给。 */
function formatDuration(hours: number): string {
  if (!Number.isFinite(hours) || hours <= 0) return "刚刚加入";
  if (hours < 24) return `${hours.toFixed(1)} 小时`;
  return `${(hours / 24).toFixed(1)} 天`;
}
