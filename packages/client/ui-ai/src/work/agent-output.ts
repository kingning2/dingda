/**
 * 工具输出 → 业务视图的解析。
 *
 * 职责：
 *   把 Agent 工具返回的原始 output（结构由后端 CLI 决定，前端不保证）解析成
 *   商品列表、比价视图、选品候选与单品鉴定，并按 id 合并进已有结果。
 *
 * 设计说明：
 *   - 「商品结果」不是后端的事件类型，所以这一步只能由知道业务语义的一方显式调用 ——
 *     reducer 不猜，本模块也不猜：解析不出来就返回空/null，由调用方决定阶段怎么走。
 *   - 解析全程容错：字段缺失、类型不对、JSON 解析失败都只丢那一条，不抛错。
 *     工具输出是外部 CLI 给的，不能假定形状。
 *   - 字段级容错统一用 `@v2/runtime/guards` 的判定器，不写 `typeof x === "string" ? x : y`。
 *     注意判定器**不转换**：所以「把数字 id 转成字符串」这类仍走 `String(...)`，
 *     两者语义不同（判定是「信任这个值」，转换是「尽量救回来」）。
 *   - 多次 compare 调用**按 item_id 累积**而不是覆盖：每一轮检索都是证据，
 *     覆盖会丢掉前几轮的对比理由与评分。
 */

import type {
  AgentWorkAppraisalItemView,
  AgentWorkAppraisalView,
  AgentWorkComparisonItemView,
  AgentWorkComparisonView,
  AgentWorkProductItem,
  AgentWorkProductsView,
  AgentWorkSelectionExcludedView,
  AgentWorkSelectionItemView,
  AgentWorkSelectionView,
} from "@v2/contracts/ai-work";
import type { CrawlProductItem } from "@v2/contracts/crawler";
import { isArray, isObject, isString } from "@v2/runtime/guards";

/**
 * 从可能混入日志的文本里捞出 JSON。
 *
 * 为什么要容错：工具侧约定「stdout 只有 JSON，日志走 stderr」（见 `tools/cli.py`），
 * 但 Agent 拿到的往往是**合并后**的输出 —— 例如 headroom 首次做内容检测时会往
 * stderr 打一行 warning，于是整段变成「日志 + JSON」。直接 `JSON.parse` 会把整批
 * 商品一起丢掉：症状是抓取其实成功、聊天里也有商品，结果面板却恒为 0 条
 * （2026-09-09 引入 headroom 后即为此症状）。
 *
 * 退两步找 JSON：① 第一个 `{` 到最后一个 `}`；② 逐行试（日志在 JSON 前后各占一行）。
 * 都失败才返回 null —— 仍不抛错，与本模块「不假定外部形状」的约定一致。
 */
function parseLooseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    /* 继续放宽 */
  }

  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start >= 0 && end > start) {
    try {
      return JSON.parse(text.slice(start, end + 1));
    } catch {
      /* 继续放宽 */
    }
  }

  for (const line of text.split("\n")) {
    const candidate = line.trim();
    if (!candidate.startsWith("{") && !candidate.startsWith("[")) continue;
    try {
      return JSON.parse(candidate);
    } catch {
      /* 试下一行 */
    }
  }
  return null;
}

/** 把 output 归一成对象；字符串先尝试 JSON.parse（容忍混入的日志行）。 */
function outputRecord(output: unknown): Record<string, unknown> | null {
  const text = isString(output, null);
  if (text !== null) {
    const parsed = parseLooseJson(text);
    return parsed === null ? null : outputRecord(parsed);
  }
  return isObject(output, null);
}

/**
 * 宽松转数字：空值与非有限数都返回 null，而不是 NaN。
 *
 * 这是**转换**不是判定 —— `asNumber("12")` 得 12，而 `isNumber("12")` 是 false。
 * 后端偶发把数字写成字符串，这里救回来。
 */
function asNumber(value: unknown): number | null {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** 有值则转字符串；`null` / `undefined` / 空串一律归 null。 */
function textOrNull(value: unknown): string | null {
  return value == null || value === "" ? null : String(value);
}

function parseComments(value: unknown): CrawlProductItem["comments"] {
  const out: NonNullable<CrawlProductItem["comments"]> = [];
  for (const row of isArray(value, [])) {
    const item = isObject(row, null);
    if (item === null) continue;
    // content / author 走 String(...) 而非判定：后端偶发把数字当文本给，
    // 判成非字符串直接丢掉反而更糟。
    const content = String(item.content ?? "").trim();
    if (!content) continue;
    out.push({
      author: String(item.author ?? "").trim() || "匿名",
      content,
      time: isString(item.time, null),
      reply: isString(item.reply, null),
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
  if (record === null) return [];
  const platform = isString(record.platform, null);
  if (platform === null) return [];
  const now = new Date().toISOString();

  // 后端有时给 items 数组，有时给单个 item —— 归一成数组。两种载荷互斥，优先 items。
  // 这一处保留三元：它是「两种载荷形状二选一」，不是类型判定，套判定器反而绕。
  const batch = isArray(record.items, null);
  const single = isObject(record.item, null);
  const rows: unknown[] = batch ?? (single === null ? [] : [single]);

  const out: CrawlProductItem[] = [];
  for (const row of rows) {
    const item = isObject(row, null);
    if (item === null) continue;
    const id = String(item.item_id ?? item.id ?? "");
    const title = String(item.title ?? "").trim();
    // id 与标题缺一不可：缺了渲染出来是个点不开的空壳。
    if (!id || !title) continue;
    out.push({
      id,
      title,
      price: String(item.price ?? ""),
      platform: platform as CrawlProductItem["platform"],
      seller: isString(item.seller_nick, undefined),
      location: isString(item.location, undefined),
      image_url: isString(item.image_url, undefined),
      // 多候选：url 优先，回落 product_url，都没有则 undefined。
      product_url: isString([item.url, item.product_url], undefined),
      want_count: isString(item.want_count, undefined),
      browse_count: isString(item.browse_count, undefined),
      desc: isString(item.desc, undefined),
      comments: parseComments(item.comments),
      ocr_text: isString(item.ocr_text, undefined),
      content_text: isString(item.content_text, undefined),
      note_type: isString(item.note_type, undefined),
      xsec_token: isString(item.xsec_token, undefined),
      crawled_at: now,
    });
  }
  return out;
}

/** 从工具输出里抽比价视图；不是 price_compare 形状就返回 null。 */
export function extractComparison(output: unknown): AgentWorkComparisonView | null {
  const record = outputRecord(output);
  if (record === null || record.kind !== "price_compare") return null;
  const rawItems = isArray(record.items, null);
  if (rawItems === null) return null;

  // 源商品信息是可选的；缺了就用空对象，下面统一按「字段可能没有」取值。
  // 注意不能写成 `isObject(record.source, {})` —— `{}` 字面量会被推成 `{}` 类型
  // （没有索引签名），后面取 `.item_id` 会报错。
  const sourceRaw: Record<string, unknown> = isObject(record.source, null) ?? {};
  const items: AgentWorkComparisonItemView[] = [];
  for (const row of rawItems) {
    const item = isObject(row, null);
    if (item === null) continue;
    const id = String(item.item_id ?? item.id ?? "").trim();
    const title = String(item.title ?? "").trim();
    if (!id || !title) continue;
    items.push({
      id,
      title,
      price: String(item.price ?? ""),
      platform: "ali1688",
      seller: isString(item.supplier, null),
      image_url: isString(item.image_url, null),
      product_url: isString(item.url, null),
      compare_label: isString(item.compare_label, null),
      compare_reasons: isArray(item.compare_reasons, [])
        .map((reason) => String(reason))
        .filter(Boolean),
      compare_score: asNumber(item.compare_score),
      similarity_score: asNumber(item.similarity_score),
      merchant_rating: asNumber(item.merchant_rating),
      repurchase_rate: asNumber(item.repurchase_rate),
      sold_count: asNumber(item.sold_count),
      yx_index: asNumber(item.yx_index),
      stock_amount: asNumber(item.stock_amount),
      quantity_begin: asNumber(item.quantity_begin),
      unit: isString(item.unit, null),
      round: asNumber(item.round),
      search_query: isString(item.search_query, null),
      search_mode: isString(item.search_mode, null),
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
      price: textOrNull(sourceRaw.price),
      seller: textOrNull(sourceRaw.seller),
    },
    items,
    total_candidates: asNumber(record.total_candidates) ?? items.length,
    rounds: asNumber(record.rounds) ?? 1,
    queries: isArray(record.queries, [])
      .map((query) => String(query))
      .filter(Boolean),
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

/** 从工具输出里抽选品视图；不是 product_selection 形状就返回 null。 */
export function extractSelection(output: unknown): AgentWorkSelectionView | null {
  const record = outputRecord(output);
  if (record === null || record.kind !== "product_selection") return null;
  const rawItems = isArray(record.candidates, null);
  if (rawItems === null) return null;

  const items: AgentWorkSelectionItemView[] = [];
  for (const row of rawItems) {
    const item = isObject(row, null);
    if (item === null) continue;
    const keyword = String(item.keyword ?? "").trim();
    const platform = String(item.platform ?? "").trim();
    if (!keyword || !platform) continue;
    items.push({
      id: `${platform}:${keyword}`,
      keyword,
      platform,
      score: asNumber(item.score),
      evidence_coverage: asNumber(item.evidence_coverage),
      sample_size: asNumber(item.sample_size) ?? 0,
      detail_size: asNumber(item.detail_size) ?? 0,
      distinct_sellers: asNumber(item.distinct_sellers) ?? 0,
      price_p25: asNumber(item.price_p25),
      price_median: asNumber(item.price_median),
      price_p75: asNumber(item.price_p75),
      demand_total: asNumber(item.demand_total),
      sold_count: asNumber(item.sold_count) ?? 0,
      on_sale_count: asNumber(item.on_sale_count) ?? 0,
      state_known: asNumber(item.state_known) ?? 0,
      availability: String(item.availability ?? ""),
      evidence_status: String(item.evidence_status ?? ""),
      reasons: textList(item.reasons),
      evidence_gaps: textList(item.evidence_gaps),
      dimensions: numberRecord(item.dimensions),
    });
  }

  const excluded: AgentWorkSelectionExcludedView[] = [];
  for (const row of isArray(record.excluded, [])) {
    const item = isObject(row, null);
    if (item === null) continue;
    const keyword = String(item.keyword ?? "").trim();
    if (!keyword) continue;
    excluded.push({
      keyword,
      platform: String(item.platform ?? "").trim(),
      error_code: String(item.error_code ?? "").trim(),
    });
  }

  const partial = record.partial === true;
  return {
    kind: "product_selection",
    platforms: textList(record.platforms),
    items,
    excluded,
    partial,
    reason: isString(record.reason, null),
    status: {
      state: items.length > 0 ? "ready" : "error",
      label: items.length > 0 ? (partial ? "已完成（不完整）" : "已完成") : "没取到样本",
      hint:
        items.length > 0
          ? `${items.length} 个候选已打分`
          : String(record.message ?? "候选都没取到可用样本"),
      badge_class:
        items.length > 0
          ? "bg-emerald-500/15 text-emerald-600"
          : "bg-red-500/15 text-red-700",
    },
  };
}

/**
 * 从工具输出里抽鉴定视图；不是 product_appraisal 形状就返回 null。
 *
 * 与 `extractSelection` 同一层判断：`kind` 对不上就整个放弃，不猜。
 */
export function extractAppraisal(output: unknown): AgentWorkAppraisalView | null {
  const record = outputRecord(output);
  if (record === null || record.kind !== "product_appraisal") return null;

  const target = appraisalRow(record.target);
  const comparables: AgentWorkAppraisalItemView[] = [];
  for (const row of isArray(record.comparables, [])) {
    const parsed = appraisalRow(row);
    if (parsed !== null) comparables.push(parsed);
  }

  // 判词是结论的主语：缺了它这张卡没什么可说的，按失败处理而不是给个空壳。
  const verdictLabel = String(record.verdict_label ?? "").trim();
  const ok = target !== null && verdictLabel !== "";

  return {
    kind: "product_appraisal",
    query: String(record.query ?? "").trim(),
    score: asNumber(record.score),
    verdict: String(record.verdict ?? "").trim(),
    verdict_label: verdictLabel,
    verdict_reason: String(record.verdict_reason ?? "").trim(),
    evidence_coverage: asNumber(record.evidence_coverage),
    dimensions: numberRecord(record.dimensions),
    reasons: textList(record.reasons),
    evidence_gaps: textList(record.evidence_gaps),
    target,
    comparables,
    spread: asNumber(record.spread),
    price_p25: asNumber(record.price_p25),
    price_median: asNumber(record.price_median),
    price_p75: asNumber(record.price_p75),
    sample_size: asNumber(record.sample_size) ?? 0,
    partial: record.partial === true,
    message: isString(record.message, null),
    status: {
      state: ok ? "ready" : "error",
      label: ok ? (record.partial === true ? "已完成（不完整）" : "已完成") : "鉴定没做成",
      hint: ok
        ? `${verdictLabel}${comparables.length > 1 ? ` · 同款 ${comparables.length - 1} 条` : ""}`
        : String(record.message ?? "本商品详情没拉到"),
      badge_class: ok
        ? "bg-emerald-500/15 text-emerald-600"
        : "bg-red-500/15 text-red-700",
    },
  };
}

/** 鉴定表一行；`item_id` 与 `title` 缺一不可 —— 缺了渲染出来点不开也认不出。 */
function appraisalRow(row: unknown): AgentWorkAppraisalItemView | null {
  const item = isObject(row, null);
  if (item === null) return null;
  const id = String(item.item_id ?? item.id ?? "").trim();
  const title = String(item.title ?? "").trim();
  if (!id || !title) return null;
  return {
    id,
    title,
    price: String(item.price ?? ""),
    platform: String(item.platform ?? ""),
    url: String(item.url ?? ""),
    seller: isString(item.seller_nick, null),
    image_url: isString(item.image_url, null),
    want_count: textOrNull(item.want_count),
    browse_count: textOrNull(item.browse_count),
    sold_state: textOrNull(item.sold_state),
    is_target: item.is_target === true,
    price_delta_pct: asNumber(item.price_delta_pct),
  };
}

/** 字符串数组；非数组或元素不是字符串就丢那一条。 */
function textList(value: unknown): string[] {
  return isArray(value, [])
    .map((entry) => String(entry ?? "").trim())
    .filter(Boolean);
}

/** 数字字典（维度分）；丢掉非数字的值，不猜。 */
function numberRecord(value: unknown): Record<string, number> {
  const record = isObject(value, null);
  if (record === null) return {};
  const out: Record<string, number> = {};
  for (const [key, entry] of Object.entries(record)) {
    const num = asNumber(entry);
    if (num !== null) out[key] = num;
  }
  return out;
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
