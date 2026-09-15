/**
 * 监控数据的展示口径：状态文案、涨跌串、时间与间隔格式化。
 *
 * 职责：
 *     把后端返回的原始值翻成界面文案；纯函数，不依赖 React / DOM，可直接单测。
 *
 * 设计说明：
 *     - 后端字段是自由字符串（`sold_state` / `state` / `kind`），这里一律**容错映射**：
 *       未收录的值原样回显，而不是硬塞一个「未知」—— 否则新状态上线时前端会静默说谎。
 *     - 价格与涨跌的**口径不在前端算**（后端已给 `price_drop`），这里只负责排版。
 *     - 时间函数要求显式传 `now`：内部读 `Date.now()` 会让这些函数无法断言。
 */

import type { MonitorTargetItem } from "@v2/contracts/monitor";

/** 徽标文案 + 配色，与 ui-primitives 的 Badge 配合使用。 */
interface ViewStyle {
  label: string;
  className: string;
}

const MUTED_CLASS = "bg-muted text-muted-foreground";

const SOLD_STATE_VIEWS: Record<string, ViewStyle> = {
  on_sale: { label: "在卖", className: "bg-emerald-500/15 text-emerald-600" },
  sold: { label: "已售出", className: "bg-sky-500/15 text-sky-600" },
  delisted: { label: "已下架", className: "bg-amber-500/15 text-amber-600" },
  gone: { label: "详情取不到", className: "bg-destructive/15 text-destructive" },
  unknown: { label: "待确认", className: MUTED_CLASS },
};

/** 售出态 → 文案 + 徽标配色；未收录的值原样回显。 */
export function soldStateView(soldState: string): ViewStyle {
  return SOLD_STATE_VIEWS[soldState] ?? { label: soldState || "待确认", className: MUTED_CLASS };
}

const MONITOR_STATE_LABELS: Record<string, string> = {
  active: "监控中",
  paused: "已暂停",
  archived: "已归档",
};

/** 监控开关状态 → 文案；未收录的值原样回显。 */
export function monitorStateLabel(state: string): string {
  return MONITOR_STATE_LABELS[state] ?? state;
}

const CHANGE_KIND_VIEWS: Record<string, ViewStyle> = {
  price_drop: { label: "降价", className: "bg-emerald-500/15 text-emerald-600" },
  price_rise: { label: "涨价", className: "bg-rose-500/15 text-rose-600" },
  sold: { label: "售出", className: "bg-sky-500/15 text-sky-600" },
  delisted: { label: "下架", className: "bg-amber-500/15 text-amber-600" },
  gone: { label: "取不到", className: "bg-destructive/15 text-destructive" },
  relisted: { label: "重新上架", className: "bg-violet-500/15 text-violet-600" },
};

/** 变更类型 → 文案 + 徽标配色；未收录的值原样回显。 */
export function changeKindView(kind: string): ViewStyle {
  return CHANGE_KIND_VIEWS[kind] ?? { label: kind || "变更", className: MUTED_CLASS };
}

/** 价格数字 → 展示串。无价格给破折号，空串会让列表看起来像加载失败。 */
export function formatPrice(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `¥${value.toFixed(2)}`;
}

/**
 * 涨跌展示串（如 `↓ ¥12.00（8.0%）`）。
 *
 * 口径取自后端：`price_drop` 为正表示「已降价」。这里不重新比较首价与现价 ——
 * 两边各算一份，一旦对不上就无从判断谁对。
 */
export function formatDrop(
  target: Pick<MonitorTargetItem, "price_drop" | "price_drop_ratio">,
): string {
  const drop = target.price_drop;
  if (drop === null || !Number.isFinite(drop) || drop === 0) return "—";
  const arrow = drop > 0 ? "↓" : "↑";
  const amount = Math.abs(drop).toFixed(2);
  const ratio = target.price_drop_ratio;
  if (ratio === null || !Number.isFinite(ratio)) return `${arrow} ¥${amount}`;
  return `${arrow} ¥${amount}（${(Math.abs(ratio) * 100).toFixed(1)}%）`;
}

/** 轮询间隔秒 → 展示串（「30 分钟」/「6 小时」/「1 天」）。 */
export function formatInterval(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`;
  if (seconds < 86_400) return `${trimZero(seconds / 3600)} 小时`;
  return `${trimZero(seconds / 86_400)} 天`;
}

/**
 * Unix **秒**时间戳 → 相对时间（「3 分钟前」/「2 天后」）。
 *
 * 两个参数都是秒：后端（Python `time.time()`）给的 `observed_at` / `last_poll_at` 就是秒，
 * 调用方传 `Date.now() / 1000`。混用毫秒会让差值差 1000 倍 —— 这个坑真的踩过，
 * 单测里「3 分钟后」被显示成「2 天后」。
 *
 * `now` 必须由调用方传入：内部读 `Date.now()` 会让这个函数无法单测。
 * 未来时间给「后」而不是负数 —— 「-3 分钟前」读起来像 bug。
 */
export function formatRelativeTime(timestamp: number, now: number): string {
  if (!Number.isFinite(timestamp) || timestamp <= 0) return "—";
  const diff = now - timestamp;
  const future = diff < 0;
  const seconds = Math.abs(diff);
  if (seconds < 60) return future ? "即将" : "刚刚";
  const suffix = future ? "后" : "前";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟${suffix}`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} 小时${suffix}`;
  return `${Math.floor(seconds / 86_400)} 天${suffix}`;
}

/** 去掉整数的小数尾巴：6.0 → "6"，1.5 → "1.5"。 */
function trimZero(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
