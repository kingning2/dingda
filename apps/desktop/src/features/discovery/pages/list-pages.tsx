/**
 * 选品发现 — 机会列表占位页。
 */

import { DataTable } from "@desk/ui";
import {
  OPPORTUNITY_TABLE_COLUMNS,
  SectionEmpty,
  type OpportunityRow,
} from "@components/product-shell";
import { DiscoveryShell } from "../discovery-shell";

export interface DiscoveryListPageProps {
  title: string;
  subtitle: string;
}

/** 高利润 / 热门 / 蓝海 / 新发现 共用列表骨架。 */
export function DiscoveryListPage({ title, subtitle }: DiscoveryListPageProps) {
  return (
    <DiscoveryShell title={title} subtitle={subtitle}>
      <DataTable<OpportunityRow>
        columns={OPPORTUNITY_TABLE_COLUMNS}
        data={[]}
        emptyText="暂无机会（骨架）— 请先连接账号并开始选品"
      />
      <SectionEmpty
        title="功能骨架"
        description="后续将在此展示结构化商品机会，而非 Agent 节点日志。"
      />
    </DiscoveryShell>
  );
}

export function DiscoveryHighProfitPage() {
  return (
    <DiscoveryListPage
      title="高利润机会"
      subtitle="按采购价、闲鱼售价、利润、利润率、竞争度筛选"
    />
  );
}

export function DiscoveryHotPage() {
  return (
    <DiscoveryListPage title="热门机会" subtitle="按市场活跃度与增长判断（骨架）" />
  );
}

export function DiscoveryBlueOceanPage() {
  return (
    <DiscoveryListPage
      title="蓝海机会"
      subtitle="需求存在 + 竞争相对较低 + 利润合理（骨架）"
    />
  );
}

export function DiscoveryNewPage() {
  return (
    <DiscoveryListPage title="新发现" subtitle="最近采集、尚未充分分析的商品（骨架）" />
  );
}
