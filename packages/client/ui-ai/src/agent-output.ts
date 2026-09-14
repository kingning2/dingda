/**
 * 工具输出 → 业务视图的解析。
 *
 * 职责：
 *   把 Agent 工具返回的原始 output（结构由后端 CLI 决定，前端不保证）解析成
 *   商品列表与比价视图，并按 id 合并进已有结果。
 *
 * 设计说明：
 *   - 「商品结果」不是后端的事件类型，所以这一步只能由知道业务语义的一方显式调用 ——
 *     reducer 不猜，本模块也不猜：解析不出来就返回空/null，由调用方决定阶段怎么走。
 *   - 解析全程容错：字段缺失、类型不对、JSON 解析失败都只丢那一条，不抛错。
 *     工具输出是外部 CLI 给的，不能假定形状。
 *   - 多次 compare 调用**按 item_id 累积**而不是覆盖：每一轮检索都是证据，
 *     覆盖会丢掉前几轮的对比理由与评分。
 */

import type {
  AgentWorkComparisonItemView,
  AgentWorkComparisonView,
  AgentWorkProductItem,
  AgentWorkProductsView,
} from "@v2/contracts/ai-work";
import type { CrawlProductItem } from "@v2/contracts/crawler";

/** 把 output 归一成对象；字符串先尝试 JSON.parse。 */
function outputRecord(output: unknown): Record<string, unknown> | null {
  if (typeof output === "string") {
    try {
      return outputRecord(JSON.parse(output));
    } catch {
      return null;
    }
  }
  if (!output || typeof output !== "object" || Array.isArray(output)) return null;
  return output as Record<string, unknown>;
}

/** 宽松转数字：空值与非有限数都返回 null，而不是 NaN。 */
function asNumber(value: unknown): number | null {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseComments(value: unknown): CrawlProductItem["comments"] {
  if (!Array.isArray(value)) return [];
  const out: NonNullable<CrawlProductItem["comments"]> = [];
  for (const row of value) {
    if (!row || typeof row !== "object") continue;
    const item = row as Record<string, unknown>;
    const content = String(item.content ?? "").trim();
    if (!content) continue;
    out.push({
      author: String(item.author ?? "").trim() || "匿名",
      content,
      time: typeof item.time === "string" ? item.time : null,
      reply: typeof item.reply === "string" ? item.reply : null,
    });
  }
  return out;
}

/**
 * 从工具输出里抽商品。
 *
 * 没有 platform 字段就直接放弃 —— 平台决定了商品该落到哪个列表，
 * 猜一个默认值会把别的平台的商品混进来。
 */
export function extractProducts(output: unknown): CrawlProductItem[] {
  const record = outputRecord(output);
  if (!record) return [];
  if (typeof record.platform !== "string" || !record.platform) return [];
  const platform = record.platform as CrawlProductItem["platform"];
  const now = new Date().toISOString();

  // 后端有时给 items 数组，有时给单个 item —— 两种都收。
  const rows: unknown[] = Array.isArray(record.items)
    ? record.items
    : record.item && typeof record.item === "object"
      ? [record.item]
      : [];

  const out: CrawlProductItem[] = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const item = row as Record<string, unknown>;
    const id = String(item.item_id ?? item.id ?? "");
    const title = String(item.title ?? "").trim();
    // id 与标题缺一不可：缺了渲染出来是个点不开的空壳。
    if (!id || !title) continue;
    out.push({
      id,
      title,
      price: String(item.price ?? ""),
      platform,
      seller: typeof item.seller_nick === "string" ? item.seller_nick : undefined,
      location: typeof item.location === "string" ? item.location : undefined,
      image_url: typeof item.image_url === "string" ? item.image_url : undefined,
      product_url:
        typeof item.url === "string"
          ? item.url
          : typeof item.product_url === "string"
            ? item.product_url
            : undefined,
      want_count: typeof item.want_count === "string" ? item.want_count : undefined,
      browse_count: typeof item.browse_count === "string" ? item.browse_count : undefined,
      desc: typeof item.desc === "string" ? item.desc : undefined,
      comments: parseComments(item.comments),
      ocr_text: typeof item.ocr_text === "string" ? item.ocr_text : undefined,
      content_text: typeof item.content_text === "string" ? item.content_text : undefined,
      note_type: typeof item.note_type === "string" ? item.note_type : undefined,
      xsec_token: typeof item.xsec_token === "string" ? item.xsec_token : undefined,
      crawled_at: now,
    });
  }
  return out;
}

/** 从工具输出里抽比价视图；不是 price_compare 形状就返回 null。 */
export function extractComparison(output: unknown): AgentWorkComparisonView | null {
  const record = outputRecord(output);
  if (!record || record.kind !== "price_compare" || !Array.isArray(record.items)) return null;

  const sourceRaw =
    record.source && typeof record.source === "object"
      ? (record.source as Record<string, unknown>)
      : {};
  const items: AgentWorkComparisonItemView[] = [];
  for (const row of record.items) {
    if (!row || typeof row !== "object") continue;
    const item = row as Record<string, unknown>;
    const id = String(item.item_id ?? item.id ?? "").trim();
    const title = String(item.title ?? "").trim();
    if (!id || !title) continue;
    items.push({
      id,
      title,
      price: String(item.price ?? ""),
      platform: "ali1688",
      seller: typeof item.supplier === "string" ? item.supplier : null,
      image_url: typeof item.image_url === "string" ? item.image_url : null,
      product_url: typeof item.url === "string" ? item.url : null,
      compare_label: typeof item.compare_label === "string" ? item.compare_label : null,
      compare_reasons: Array.isArray(item.compare_reasons)
        ? item.compare_reasons.map((reason) => String(reason)).filter(Boolean)
        : [],
      compare_score: asNumber(item.compare_score),
      similarity_score: asNumber(item.similarity_score),
      merchant_rating: asNumber(item.merchant_rating),
      repurchase_rate: asNumber(item.repurchase_rate),
      sold_count: asNumber(item.sold_count),
      yx_index: asNumber(item.yx_index),
      stock_amount: asNumber(item.stock_amount),
      quantity_begin: asNumber(item.quantity_begin),
      unit: typeof item.unit === "string" ? item.unit : null,
      round: asNumber(item.round),
      search_query: typeof item.search_query === "string" ? item.search_query : null,
      search_mode: typeof item.search_mode === "string" ? item.search_mode : null,
    });
  }

  return {
    kind: "price_compare",
    platform: String(record.platform || "ali1688"),
    source: {
      item_id: String(sourceRaw.item_id ?? ""),
      title: String(sourceRaw.title ?? ""),
      platform: String(sourceRaw.platform ?? "source"),
      url: String(sourceRaw.url ?? record.source_url ?? ""),
      image_url: String(sourceRaw.image_url ?? record.source_image ?? ""),
      price: sourceRaw.price == null || sourceRaw.price === "" ? null : String(sourceRaw.price),
      seller:
        sourceRaw.seller == null || sourceRaw.seller === "" ? null : String(sourceRaw.seller),
    },
    items,
    total_candidates: asNumber(record.total_candidates) ?? items.length,
    rounds: asNumber(record.rounds) ?? 1,
    queries: Array.isArray(record.queries)
      ? record.queries.map((query) => String(query)).filter(Boolean)
      : [],
    status: {
      state: "ready",
      label: "已完成",
      hint: `${items.length} 款对比`,
      badge_class: "bg-emerald-500/15 text-emerald-600",
    },
  };
}

/** 多次 compare 调用按 item_id 累积，保留每一轮证据而不是覆盖。 */
export function mergeComparison(
  current: AgentWorkComparisonView | null | undefined,
  next: AgentWorkComparisonView,
): AgentWorkComparisonView {
  if (!current) return next;

  const roundOffset = current.rounds ?? 0;
  const byId = new Map(current.items.map((item) => [item.id, item]));
  for (const item of next.items) {
    const existing = byId.get(item.id);
    const round = roundOffset + (item.round ?? 1);
    if (!existing) {
      byId.set(item.id, { ...item, round });
      continue;
    }
    byId.set(item.id, {
      ...existing,
      ...item,
      // 保留最早出现的轮次：同一个商品在后续轮次再次命中，说明它一开始就被检索到了。
      round: Math.min(existing.round ?? round, round),
      compare_reasons: [...new Set([...existing.compare_reasons, ...item.compare_reasons])],
      // 数值字段取「先有的非空值」，避免后续轮次的空值把已有数据抹掉。
      compare_score: item.compare_score ?? existing.compare_score,
      merchant_rating: item.merchant_rating ?? existing.merchant_rating,
      repurchase_rate: item.repurchase_rate ?? existing.repurchase_rate,
      sold_count: item.sold_count ?? existing.sold_count,
      yx_index: item.yx_index ?? existing.yx_index,
      stock_amount: item.stock_amount ?? existing.stock_amount,
      quantity_begin: item.quantity_begin ?? existing.quantity_begin,
    });
  }

  return {
    ...next,
    // 本轮没给源商品信息就沿用上一轮的，否则右侧「对比源」会变空。
    source: next.source.title || next.source.image_url ? next.source : current.source,
    items: [...byId.values()],
    total_candidates: current.total_candidates + next.total_candidates,
    rounds: roundOffset + next.rounds,
    queries: [...(current.queries ?? []), ...next.queries],
  };
}

/**
 * 把新采到的商品并进已有列表，并打上来源步骤。
 *
 * 空数组直接返回原对象（保持引用不变）：调用方据此避免无意义的状态更新。
 */
export function mergeProducts(
  current: AgentWorkProductsView,
  items: CrawlProductItem[],
  stepId: string,
): AgentWorkProductsView {
  if (items.length === 0) return current;
  const byId = new Map<string, AgentWorkProductItem>(current.items.map((item) => [item.id, item]));
  for (const item of items) {
    byId.set(item.id, { ...item, step_id: stepId });
  }
  const merged = [...byId.values()];
  return {
    ...current,
    items: merged,
    total: merged.length,
    status: {
      state: "ready",
      label: "已采集",
      hint: `共 ${merged.length} 条`,
      badge_class: "bg-emerald-500/15 text-emerald-600",
    },
  };
}
