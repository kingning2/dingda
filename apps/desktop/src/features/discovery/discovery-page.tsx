/**
 * 比价选品页 — 闲鱼（需求）× 1688（货源）跨平台套利发现。
 *
 * 骨架占位：后续接入 `platforms/discovery` 的 IPC 命令。
 */

import { BentoCard, BentoGrid, PageScaffold, SpotlightCard } from "@desk/ui";
import { Package, Repeat, Search, Star } from "@desk/ui/icons";

/** 比价选品页。 */
export function DiscoveryPage() {
  return (
    <PageScaffold
      title="比价选品"
      subtitle="闲鱼强需求商品 × 1688 低价货源，自动比价入库"
    >
      <BentoGrid columns={3}>
        <BentoCard colSpan={2} glow className="min-h-[200px]">
          <div className="flex items-start gap-3">
            <Star className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
            <div>
              <h2 className="text-[length:var(--text-sm)] font-medium text-foreground">
                发现循环
              </h2>
              <p className="mt-2 text-[length:var(--text-sm)] text-muted-foreground">
                在此配置关键词、目标利润率与自动入库规则，系统将循环扫描并推荐可套利商品。
              </p>
            </div>
          </div>
        </BentoCard>

        <SpotlightCard className="min-h-[200px] border border-border/70 bg-card/80 p-5 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <Repeat className="size-4 text-primary" aria-hidden />
            <h3 className="text-[length:var(--text-sm)] font-medium">双平台对比</h3>
          </div>
          <p className="mt-3 text-[length:var(--text-xs)] text-muted-foreground">
            闲鱼需求侧 × 1688 供给侧价差分析
          </p>
        </SpotlightCard>
      </BentoGrid>

      <BentoGrid columns={2} className="mt-4">
        <BentoCard glow>
          <div className="flex items-center gap-2">
            <Search className="size-4 text-primary" aria-hidden />
            <h3 className="text-[length:var(--text-sm)] font-medium">闲鱼需求采集</h3>
          </div>
          <p className="mt-2 text-[length:var(--text-xs)] text-muted-foreground">
            即将推出：按关键词扫描闲鱼需求、分析热度与买家询价
          </p>
        </BentoCard>
        <BentoCard glow>
          <div className="flex items-center gap-2">
            <Package className="size-4 text-primary" aria-hidden />
            <h3 className="text-[length:var(--text-sm)] font-medium">1688 货源匹配</h3>
          </div>
          <p className="mt-2 text-[length:var(--text-xs)] text-muted-foreground">
            即将推出：匹配 1688 同款货源并估算进货成本
          </p>
        </BentoCard>
      </BentoGrid>
    </PageScaffold>
  );
}
