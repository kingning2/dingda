/**
 * 右侧鉴定结果：一个具体商品的判词卡 + 同款横向对比表。
 *
 * 职责：
 *   把 `appraise_item` 的判词摊开给人看 —— 结论（四态判词 + 分 + 证据覆盖）为什么是
 *   这个结论（reasons）、哪几项没量到（evidence_gaps），以及**参照系长什么样**：
 *   一批同款按价格升序排开，本商品自己插在它的价格位置上。
 *
 * 设计说明：
 *   - **本商品自己也在同款表里**（高亮 + 「本商品」标记）。这一列存在的意义是回答转卖
 *     决策的第二半 —— 「还有没有更便宜的同类」：看得到比本商品便宜的同款，说明这个价
 *     还能再谈；看不到，才算真的便宜。
 *   - **没量到的字段显示成「—」不是 0**（与选品面板同一约定）：0 会被读成「量过且很差」。
 *   - **判词不许改口径**：直接显示后端给的 `verdict_label`，前端不升级也不降级。
 *   - 价差是**毛价差**（不含闲鱼手续费、运费与压货时间），所以底部的免责声明必须写到
 *     这一层，不能让人把它当成「能赚多少」。
 */

import { Badge } from "@v2/ui-primitives/badge";
import { Card, CardContent } from "@v2/ui-primitives/card";
import { cn } from "@v2/ui-primitives/utils";
import type {
  AgentWorkAppraisalItemView,
  AgentWorkAppraisalView,
} from "@v2/contracts/ai-work";

const DIMENSION_LABELS: Record<string, string> = {
  margin: "价差空间",
  demand: "需求热度",
  competition: "竞争密度",
  sold: "售出验证",
};

const SOLD_STATE_LABELS: Record<string, string> = {
  on_sale: "在售",
  sold: "已售",
  delisted: "已下架",
  gone: "已失效",
};

const PLATFORM_LABELS: Record<string, string> = {
  xianyu: "闲鱼",
  xiaohongshu: "小红书",
  ali1688: "1688",
};

function platformLabel(platform: string): string {
  return PLATFORM_LABELS[platform] ?? platform;
}

/** 判词 → 配色。四种判词都配一个色，别让「判不了」长得像「不值得」。 */
function verdictTone(verdict: string): string {
  switch (verdict) {
    case "worth":
      return "bg-emerald-500/15 text-emerald-700";
    case "caution":
      return "bg-amber-500/15 text-amber-800";
    case "skip":
      return "bg-red-500/15 text-red-700";
    default:
      return "bg-muted text-muted-foreground";
  }
}

/** 相对本商品价的涨跌；本商品自己与没量到价格的同款都显示「—」。 */
function formatDelta(delta: number | null | undefined, isTarget: boolean): string {
  if (isTarget) return "本商品";
  if (delta == null) return "—";
  if (delta === 0) return "同价";
  return delta > 0 ? `贵 ${delta.toFixed(0)}%` : `便宜 ${Math.abs(delta).toFixed(0)}%`;
}

/** 计数列：空值给「—」，不拿 0 冒充量到。 */
function textOr(value: string | null | undefined): string {
  const text = (value ?? "").trim();
  return text === "" ? "—" : text;
}

function ComparableRow({ row }: { row: AgentWorkAppraisalItemView }) {
  return (
    <div
      className={cn(
        "grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 rounded-md px-2.5 py-2",
        row.is_target ? "bg-primary/10 ring-1 ring-primary/30" : "odd:bg-muted/40",
      )}
    >
      <div className="min-w-0">
        <p className="truncate text-[12px] text-foreground" title={row.title}>
          {row.title}
        </p>
        <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
          {row.seller ? `${row.seller} · ` : ""}
          想要 {textOr(row.want_count)} · 浏览 {textOr(row.browse_count)} ·{" "}
          {SOLD_STATE_LABELS[row.sold_state ?? ""] ?? "—"}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-[12px] font-medium text-foreground">
          {textOr(row.price) === "—" ? "—" : `¥${row.price}`}
        </p>
        <p
          className={cn(
            "mt-0.5 text-[10px]",
            row.is_target ? "text-primary" : "text-muted-foreground",
          )}
        >
          {formatDelta(row.price_delta_pct, row.is_target)}
        </p>
      </div>
    </div>
  );
}

function FailureCard({ appraisal }: { appraisal: AgentWorkAppraisalView }) {
  return (
    <Card size="sm" className="ring-border/70">
      <CardContent className="space-y-1.5">
        <p className="text-sm font-semibold text-foreground">这一件没鉴定成</p>
        <p className="text-[11px] text-muted-foreground">
          {appraisal.message ?? "本商品详情没拉到，什么都算不出来。"}
        </p>
      </CardContent>
    </Card>
  );
}

/** 右侧鉴定面板。 */
export function AppraisalResults({ appraisal }: { appraisal: AgentWorkAppraisalView }) {
  const target = appraisal.target;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-start justify-between gap-3 border-b border-border/70 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">商品鉴定</h2>
          <p className="mt-0.5 truncate text-xs text-muted-foreground" title={appraisal.query}>
            同款检索词：{appraisal.query || "—"}
          </p>
        </div>
        <Badge className={cn("shrink-0 border-transparent", appraisal.status.badge_class)}>
          {appraisal.status.label}
        </Badge>
      </header>

      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-4 py-4">
        {appraisal.partial ? (
          <p className="rounded-md bg-amber-500/10 px-2.5 py-2 text-[11px] text-amber-800">
            这一轮没跑完（预算用完或被取消），下面的对比不完整。
          </p>
        ) : null}

        {target === null ? (
          <FailureCard appraisal={appraisal} />
        ) : (
          <Card size="sm" className="ring-border/70">
            <CardContent className="space-y-2.5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <Badge
                    className={cn(
                      "shrink-0 border-transparent py-0 text-[11px]",
                      verdictTone(appraisal.verdict),
                    )}
                  >
                    {appraisal.verdict_label}
                  </Badge>
                  <p className="mt-1.5 truncate text-sm font-semibold text-foreground" title={target.title}>
                    {target.title}
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {platformLabel(target.platform)} · ¥{target.price || "—"} ·{" "}
                    {target.seller || "卖家未知"}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-lg leading-none font-semibold text-foreground">
                    {appraisal.score == null ? "—" : appraisal.score.toFixed(1)}
                  </p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">
                    {appraisal.evidence_coverage == null
                      ? "无分"
                      : `证据覆盖 ${Math.round(appraisal.evidence_coverage * 100)}%`}
                  </p>
                </div>
              </div>

              <p className="text-[11px] text-foreground">{appraisal.verdict_reason}</p>

              <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 border-t border-border/60 pt-2 text-[11px]">
                <Metric
                  label="同款中位价"
                  value={appraisal.price_median == null ? "—" : `¥${Math.round(appraisal.price_median)}`}
                />
                <Metric
                  label="价格带"
                  value={
                    appraisal.price_p25 == null || appraisal.price_p75 == null
                      ? "—"
                      : `¥${Math.round(appraisal.price_p25)} ~ ${Math.round(appraisal.price_p75)}`
                  }
                />
                <Metric
                  label="比同款"
                  value={
                    appraisal.spread == null
                      ? "—"
                      : appraisal.spread >= 0
                        ? `低 ${(appraisal.spread * 100).toFixed(0)}%`
                        : `高 ${Math.abs(appraisal.spread * 100).toFixed(0)}%`
                  }
                />
                <Metric label="同款条数" value={String(appraisal.sample_size)} />
              </dl>

              {Object.keys(appraisal.dimensions).length > 0 ? (
                <p className="text-[10px] text-muted-foreground">
                  {Object.keys(DIMENSION_LABELS)
                    .filter((key) => key in appraisal.dimensions)
                    .map((key) => `${DIMENSION_LABELS[key]} ${appraisal.dimensions[key]?.toFixed(2)}`)
                    .join(" · ")}
                </p>
              ) : null}
            </CardContent>
          </Card>
        )}

        {appraisal.reasons.length > 0 ? (
          <Card size="sm" className="ring-border/70">
            <CardContent className="space-y-1">
              <p className="text-[11px] font-medium text-foreground">算分依据</p>
              <ul className="space-y-0.5 text-[11px] text-muted-foreground">
                {appraisal.reasons.map((reason) => (
                  <li key={reason} className="flex gap-1.5">
                    <span className="shrink-0">·</span>
                    <span className="min-w-0">{reason}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ) : null}

        {appraisal.evidence_gaps.length > 0 ? (
          <ul className="space-y-0.5 rounded-md bg-amber-500/10 px-2.5 py-2 text-[11px] text-amber-800">
            {appraisal.evidence_gaps.map((gap) => (
              <li key={gap} className="flex gap-1.5">
                <span className="shrink-0">缺</span>
                <span className="min-w-0">{gap}</span>
              </li>
            ))}
          </ul>
        ) : null}

        {appraisal.comparables.length > 0 ? (
          <Card size="sm" className="ring-border/70">
            <CardContent className="space-y-1.5">
              <div>
                <p className="text-[11px] font-medium text-foreground">同款对比（价格升序）</p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  本商品自己也在表里；有比它便宜的同款，说明这个价还能再谈。
                </p>
              </div>
              <div className="space-y-0.5">
                {appraisal.comparables.map((row) => (
                  <ComparableRow key={`${row.id}:${row.is_target ? "target" : "peer"}`} row={row} />
                ))}
              </div>
            </CardContent>
          </Card>
        ) : null}

        <p className="pt-1 text-[10px] leading-relaxed text-muted-foreground">
          价差是毛价差：只比了同款标价，不含闲鱼手续费、运费与压货时间，不等于能赚多少。
          需求与售出这两项靠有限几条同款量出来，样本薄，置信度不高 —— 没量到的维度已在上面
          如实列出。
        </p>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="truncate text-foreground" title={value}>
        {value}
      </dd>
    </div>
  );
}
