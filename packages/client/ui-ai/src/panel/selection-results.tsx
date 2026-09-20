/**
 * 右侧选品结果：候选品类按综合分排名的表。
 *
 * 职责：
 *   把 `select_products` 的量分结果摊开给人看 —— 每个候选一行，带上它凭什么得这个分
 *   （reasons）、以及哪几项没量到（evidence_gaps）。**这是选品结论的全部依据**，
 *   正文里出现的品类必须能在这一表里找到行。
 *
 * 设计说明：
 *   - **分数只在同一平台内可比**，所以先按平台分组再按分排；跨平台的行不会混在一起
 *     比大小，分组标题上也写明这件事。
 *   - **没量到的维度照实显示成「—」**，不显示 0：0 会被读成「量过且很差」，
 *     这两个意思差很远。
 *   - 覆盖率（evidence_coverage）单独一列：同样是 70 分，量了四个维度得的 70 分
 *     和只量到一个维度的 70 分不是一回事。
 */

import { Badge } from "@v2/ui-primitives/badge";
import { Card, CardContent } from "@v2/ui-primitives/card";
import { cn } from "@v2/ui-primitives/utils";
import type {
  AgentWorkSelectionItemView,
  AgentWorkSelectionView,
} from "@v2/contracts/ai-work";

/** 维度名 → 表格列标题。顺序就是列顺序，没量到的维度不出现在这张表里。 */
const DIMENSION_LABELS: Record<string, string> = {
  demand: "需求热度",
  competition: "竞争密度",
  entry: "入手门槛",
  sold: "售出验证",
};

const PLATFORM_LABELS: Record<string, string> = {
  xianyu: "闲鱼",
  xiaohongshu: "小红书",
  ali1688: "1688",
};

const AVAILABILITY_LABELS: Record<string, string> = {
  unverified: "未验证",
};

function platformLabel(platform: string): string {
  return PLATFORM_LABELS[platform] ?? platform;
}

/** 千分位；非数字给「—」。 */
function formatCount(value: number | null): string {
  return value == null ? "—" : value.toLocaleString("zh-CN");
}

/** 价格带；三档都有才算得出区间。 */
function formatPriceBand(item: AgentWorkSelectionItemView): string {
  if (item.price_median == null) return "—";
  const median = Math.round(item.price_median);
  if (item.price_p25 == null || item.price_p75 == null) return `¥${median}`;
  return `¥${Math.round(item.price_p25)} ~ ${Math.round(item.price_p75)}（中位 ${median}）`;
}

/** 售出比例：分母是「量到状态的条数」，不是样本总数。 */
function formatSold(item: AgentWorkSelectionItemView): string {
  if (item.state_known === 0) return "—";
  return `${item.sold_count} / ${item.state_known}`;
}

function CandidateCard({ item, rank }: { item: AgentWorkSelectionItemView; rank: number }) {
  const dimensions = Object.keys(DIMENSION_LABELS).filter((key) => key in item.dimensions);

  return (
    <Card size="sm" className="ring-border/70">
      <CardContent className="space-y-2.5">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <Badge variant="outline" className="shrink-0 py-0 text-[10px]">
                {rank}
              </Badge>
              <h3 className="truncate text-sm font-semibold text-foreground">{item.keyword}</h3>
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {platformLabel(item.platform)} · 样本 {item.sample_size} 条 /{" "}
              {item.distinct_sellers} 个卖家 · 货源
              {AVAILABILITY_LABELS[item.availability] ?? item.availability}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-lg leading-none font-semibold text-foreground">
              {item.score == null ? "—" : item.score.toFixed(1)}
            </p>
            <p className="mt-0.5 text-[10px] text-muted-foreground">
              {item.evidence_coverage == null
                ? "无分"
                : `证据覆盖 ${Math.round(item.evidence_coverage * 100)}%`}
            </p>
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px]">
          <Metric label="价格带" value={formatPriceBand(item)} />
          <Metric label="需求热度" value={formatCount(item.demand_total)} />
          <Metric label="已售 / 下架" value={formatSold(item)} />
          <Metric
            label="维度得分"
            value={
              dimensions.length === 0
                ? "—"
                : dimensions
                    .map((key) => `${DIMENSION_LABELS[key]} ${item.dimensions[key]?.toFixed(2)}`)
                    .join(" · ")
            }
          />
        </dl>

        {item.reasons.length > 0 ? (
          <ul className="space-y-0.5 border-t border-border/60 pt-2 text-[11px] text-muted-foreground">
            {item.reasons.map((reason) => (
              <li key={reason} className="flex gap-1.5">
                <span className="shrink-0">·</span>
                <span className="min-w-0">{reason}</span>
              </li>
            ))}
          </ul>
        ) : null}

        {item.evidence_gaps.length > 0 ? (
          <ul className="space-y-0.5 rounded-md bg-amber-500/10 px-2 py-1.5 text-[11px] text-amber-800">
            {item.evidence_gaps.map((gap) => (
              <li key={gap} className="flex gap-1.5">
                <span className="shrink-0">缺</span>
                <span className="min-w-0">{gap}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
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

/** 右侧选品面板。 */
export function SelectionResults({ selection }: { selection: AgentWorkSelectionView }) {
  const platforms = selection.platforms.length > 0 ? selection.platforms : [...new Set(selection.items.map((item) => item.platform))];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-start justify-between gap-3 border-b border-border/70 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">选品候选排名</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {platforms.map(platformLabel).join(" / ")}
            {platforms.length > 1 ? " · 分数只在同一平台内可比" : " · 分数为该平台内归一"}
          </p>
        </div>
        <Badge className={cn("shrink-0 border-transparent", selection.status.badge_class)}>
          {selection.status.label}
        </Badge>
      </header>

      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-4 py-4">
        {selection.reason ? (
          <p className="text-[11px] text-muted-foreground">挑这些候选的理由：{selection.reason}</p>
        ) : null}

        {selection.partial ? (
          <p className="rounded-md bg-amber-500/10 px-2.5 py-2 text-[11px] text-amber-800">
            这一轮没跑完（预算用完或被取消），下面的排名不完整。
          </p>
        ) : null}

        {selection.items.map((item, index) => (
          <CandidateCard key={item.id} item={item} rank={index + 1} />
        ))}

        {selection.excluded.length > 0 ? (
          <div className="rounded-md border border-dashed border-border/70 px-3 py-2.5">
            <p className="text-[11px] font-medium text-foreground">没取到样本的候选</p>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              这些词搜不到结果或抓取失败，没有分，别拿它们下结论。
            </p>
            <ul className="mt-1.5 space-y-0.5 text-[11px] text-muted-foreground">
              {selection.excluded.map((row) => (
                <li key={`${row.platform}:${row.keyword}`}>
                  {row.keyword}（{platformLabel(row.platform)}）· {row.error_code}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <p className="pt-1 text-[10px] leading-relaxed text-muted-foreground">
          这些分是需求侧代理指标（想要数 / 竞争条数 / 价格带 / 售出状态），不是真实销量与利润。
          它能筛掉一眼假的品类，不能保证赚钱。
        </p>
      </div>
    </div>
  );
}
