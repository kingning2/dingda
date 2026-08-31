/**
 * 右侧分析面板 — 结果 / 商品 / 建议。
 */

import { useMemo, useState } from "react";
import type { AgentRunRecord } from "@desk/platform/ipc/agent-run";
import { TypewriterText } from "@desk/ui";

import {
  parseCrawlContent,
  parseWebResearchContent,
  stateLabel,
} from "../price-compare";
import { resultsStyles as s } from "./styles";

type ResultsTab = "summary" | "products" | "advice";

export interface ResultsPanelProps {
  record: AgentRunRecord | null;
  replyText?: string;
  replyStreaming?: boolean;
  productCount?: number;
}

export function ResultsPanel({
  record,
  replyText,
  replyStreaming,
  productCount,
}: ResultsPanelProps) {
  const [tab, setTab] = useState<ResultsTab>("summary");

  const crawl = useMemo(() => {
    const step = record?.steps.find((item) => item.node === "crawl");
    return parseCrawlContent(step?.content);
  }, [record]);

  const research = useMemo(() => {
    const step = record?.steps.find((item) => item.node === "web_research");
    return parseWebResearchContent(step?.content);
  }, [record]);

  const items = crawl?.items ?? [];
  const count = productCount ?? items.length;

  if (!record) {
    return (
      <aside style={s.aside}>
        <div style={s.empty}>
          <p style={s.emptyTitle}>分析面板</p>
          <p style={s.emptyText}>发起比价后，这里会展示结构化结果与商品列表。</p>
        </div>
      </aside>
    );
  }

  return (
    <aside style={s.aside}>
      <div style={s.header}>
        <p style={s.headerTitle}>分析结果</p>
        <p style={s.headerMeta}>
          {stateLabel(record.state)}
          {count > 0 ? ` · ${count} 件商品` : ""}
        </p>
      </div>

      <div style={s.tabs} role="tablist">
        {(
          [
            ["summary", "分析结果"],
            ["products", `商品列表${count > 0 ? ` (${count})` : ""}`],
            ["advice", "购买建议"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            style={s.tab(tab === id)}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div style={s.body}>
        {tab === "summary" ? (
          <div style={s.section}>
            {count > 0 ? (
              <div style={s.card}>
                <p style={s.cardTitle}>商品概览</p>
                <p style={s.cardBody}>已采集 {count} 件商品，详见「商品列表」。</p>
              </div>
            ) : null}
            {research && research.sources.length > 0 ? (
              <div style={s.card}>
                <p style={s.cardTitle}>参考来源 ({research.sources.length})</p>
                <ul style={s.sourceList}>
                  {research.sources.slice(0, 6).map((source) => (
                    <li key={source.url || source.title} style={s.sourceItem}>
                      {source.url ? (
                        <a href={source.url} target="_blank" rel="noreferrer" style={s.sourceLink}>
                          {source.title}
                        </a>
                      ) : (
                        source.title
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {count === 0 && (!research || research.sources.length === 0) ? (
              <p style={s.placeholder}>分析进行中，结构化结果将在此更新…</p>
            ) : null}
          </div>
        ) : null}

        {tab === "products" ? (
          <div style={s.productGrid}>
            {items.length === 0 ? (
              <p style={s.placeholder}>暂无商品数据</p>
            ) : (
              items.map((item) => (
                <article key={`${item.platform ?? ""}-${item.url || item.title}`} style={s.productCard}>
                  <p style={s.productPlatform}>{item.platform || "渠道"}</p>
                  <p style={s.productTitle}>
                    {item.url ? (
                      <a href={item.url} target="_blank" rel="noreferrer" style={s.sourceLink}>
                        {item.title}
                      </a>
                    ) : (
                      item.title
                    )}
                  </p>
                  {item.price ? <p style={s.productPrice}>{item.price}</p> : null}
                  {item.snippet ? <p style={s.productSnippet}>{item.snippet}</p> : null}
                </article>
              ))
            )}
          </div>
        ) : null}

        {tab === "advice" ? (
          <div style={s.section}>
            {replyText?.trim() ? (
              <div style={s.card}>
                <p style={s.cardTitle}>分析结论</p>
                <p style={s.cardBody}>
                  <TypewriterText text={replyText} streaming={Boolean(replyStreaming)} />
                </p>
              </div>
            ) : (
              <p style={s.placeholder}>任务完成后将生成购买建议</p>
            )}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
