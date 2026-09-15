/**
 * 采集域 HTTP API：单品详情。
 *
 * 职责：
 *     调 Python Crawler 拉单个商品详情（价格、想要人数、留言等），供预览浮层使用。
 *
 * 设计说明：
 *     只留非流式的 `fetchCrawlerProduct`。原先还有 SSE 版的搜品与详情直播
 *     （`searchCrawlerProductsLive` / `fetchCrawlerProductLive`）：前者唯一的消费者是
 *     已被监控页取代的爬虫搜索页，后者从未接线。两个随页面一起删掉，
 *     不留一段没人调的流式代码（流式与统一 http-client 是两条路径，维护成本翻倍）。
 */

import type { CrawlProductRequest, CrawlProductResponse } from "@v2/contracts/crawler";
import { api } from "@v2/runtime/http-client";

/** 单品详情（闲鱼价格 / 想要人数等）。 */
export async function fetchCrawlerProduct(
  request: CrawlProductRequest,
  options?: { signal?: AbortSignal },
): Promise<CrawlProductResponse> {
  const { data } = await api.post<CrawlProductResponse>(
    "/v1/crawler/product",
    {
      platform: request.platform,
      item_id: request.item_id,
      cookie: request.cookie ?? null,
      xsec_token: request.xsec_token ?? null,
    },
    {
      signal: options?.signal,
      timeoutMs: 60_000,
      fallbackError: "商品详情失败",
      skipErrorToast: true,
    },
  );
  return data;
}
