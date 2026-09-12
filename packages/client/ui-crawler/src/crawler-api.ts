import type {
  CrawlPlatform,
  CrawlProductItem,
  CrawlProductRequest,
  CrawlProductResponse,
  CrawlSearchRequest,
  CrawlSearchResponse,
} from "@v2/contracts/crawler";
import { api, getApiBaseUrl } from "@v2/runtime/http-client";

/** 调用 Python Crawler 搜品（POST /v1/crawler/search）。 */
export async function searchCrawlerProducts(
  request: CrawlSearchRequest,
  options?: { signal?: AbortSignal },
): Promise<CrawlSearchResponse> {
  const { data } = await api.post<CrawlSearchResponse>(
    "/v1/crawler/search",
    {
      platform: request.platform,
      query: request.query,
      limit: request.limit ?? 12,
      cookie: request.cookie ?? null,
    },
    {
      signal: options?.signal,
      timeoutMs: 90_000,
      fallbackError: "爬虫搜品失败",
      skipErrorToast: true,
    },
  );
  return data;
}

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

/**
 * 直播拉详情：SSE 推送浏览器截图帧，最终给出详情结果。
 * 小红书会打开笔记弹层卡片；闲鱼多为 API，可能几乎无帧。
 */
export async function fetchCrawlerProductLive(
  request: CrawlProductRequest,
  handlers: CrawlerProductLiveHandlers,
  options?: { signal?: AbortSignal },
): Promise<CrawlProductResponse> {
  const base = getApiBaseUrl()?.replace(/\/$/, "");
  if (!base) {
    throw new Error("服务未就绪，无法发起详情直播");
  }

  const response = await fetch(`${base}/v1/crawler/product/live`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      platform: request.platform,
      item_id: request.item_id,
      cookie: request.cookie ?? null,
      xsec_token: request.xsec_token ?? null,
    }),
    signal: options?.signal,
  });

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => "");
    throw new Error(text.trim() || `详情直播失败（${response.status}）`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: CrawlProductResponse | null = null;
  let fatal: Error | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      for (const evt of parseSseChunk(part)) {
        let payload: unknown = null;
        try {
          payload = JSON.parse(evt.data) as unknown;
        } catch {
          continue;
        }

        if (evt.event === "status" && payload && typeof payload === "object") {
          handlers.onStatus?.(payload as {
            state: string;
            label: string;
            hint?: string | null;
            search_url?: string | null;
          });
          continue;
        }

        if (evt.event === "frame" && payload && typeof payload === "object") {
          const frame = payload as CrawlerLiveFrame;
          if (frame.image_b64) {
            handlers.onFrame?.(frame);
          }
          continue;
        }

        if (evt.event === "result" && payload && typeof payload === "object") {
          finalResult = payload as CrawlProductResponse;
          handlers.onResult?.(finalResult);
          continue;
        }

        if (evt.event === "error" && payload && typeof payload === "object") {
          const err = payload as {
            error_code?: string | null;
            message?: string;
          };
          const message = err.message?.trim() || "商品详情失败";
          handlers.onError?.({
            error_code: err.error_code,
            message,
          });
          fatal = new Error(message);
          continue;
        }
      }
    }
  }

  if (fatal && !finalResult) throw fatal;
  if (finalResult) return finalResult;

  return {
    ok: false,
    platform: request.platform,
    item: null,
    error_code: "tool.failed",
    message: "详情直播流未返回结果",
  };
}

export interface CrawlerLiveFrame {
  url: string;
  title: string;
  hint?: string | null;
  mime: string;
  image_b64: string;
}

type CrawlerLiveStatus = {
  state: string;
  label: string;
  hint?: string | null;
  search_url?: string | null;
};

type CrawlerLiveError = {
  error_code?: string | null;
  message: string;
  search_url?: string | null;
};

/** 搜品直播回调。 */
export interface CrawlerSearchLiveHandlers {
  onStatus?: (payload: CrawlerLiveStatus) => void;
  onFrame?: (frame: CrawlerLiveFrame) => void;
  onResult?: (result: CrawlSearchResponse) => void;
  onError?: (payload: CrawlerLiveError) => void;
}

/** 详情直播回调。 */
export interface CrawlerProductLiveHandlers {
  onStatus?: (payload: CrawlerLiveStatus) => void;
  onFrame?: (frame: CrawlerLiveFrame) => void;
  onResult?: (result: CrawlProductResponse) => void;
  onError?: (payload: CrawlerLiveError) => void;
}

function frameToDataUrl(frame: CrawlerLiveFrame): string {
  return `data:${frame.mime || "image/jpeg"};base64,${frame.image_b64}`;
}

export function crawlerLiveFrameToDataUrl(frame: CrawlerLiveFrame): string {
  return frameToDataUrl(frame);
}

/** 解析 SSE 文本块。 */
function parseSseChunk(chunk: string): Array<{ event: string; data: string }> {
  const events: Array<{ event: string; data: string }> = [];
  const blocks = chunk.split("\n\n");
  for (const block of blocks) {
    const trimmed = block.trim();
    if (!trimmed) continue;
    let event = "message";
    const dataLines: string[] = [];
    for (const line of trimmed.split("\n")) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (dataLines.length > 0) {
      events.push({ event, data: dataLines.join("\n") });
    }
  }
  return events;
}

/**
 * 直播搜品：SSE 推送浏览器截图帧，最终给出商品列表。
 * 浏览器平台（闲鱼/小红书）会持续推 frame；1688 多为 API，可能几乎无帧。
 */
export async function searchCrawlerProductsLive(
  request: CrawlSearchRequest,
  handlers: CrawlerSearchLiveHandlers,
  options?: { signal?: AbortSignal },
): Promise<CrawlSearchResponse> {
  const base = getApiBaseUrl()?.replace(/\/$/, "");
  if (!base) {
    throw new Error("服务未就绪，无法发起爬虫直播");
  }

  const response = await fetch(`${base}/v1/crawler/search/live`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      platform: request.platform,
      query: request.query,
      limit: request.limit ?? 12,
      cookie: request.cookie ?? null,
    }),
    signal: options?.signal,
  });

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => "");
    throw new Error(text.trim() || `爬虫直播失败（${response.status}）`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: CrawlSearchResponse | null = null;
  let fatal: Error | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      for (const evt of parseSseChunk(part)) {
        let payload: unknown = null;
        try {
          payload = JSON.parse(evt.data) as unknown;
        } catch {
          continue;
        }

        if (evt.event === "status" && payload && typeof payload === "object") {
          handlers.onStatus?.(payload as {
            state: string;
            label: string;
            hint?: string | null;
            search_url?: string | null;
          });
          continue;
        }

        if (evt.event === "frame" && payload && typeof payload === "object") {
          const frame = payload as CrawlerLiveFrame;
          if (frame.image_b64) {
            handlers.onFrame?.(frame);
          }
          continue;
        }

        if (evt.event === "result" && payload && typeof payload === "object") {
          finalResult = payload as CrawlSearchResponse;
          handlers.onResult?.(finalResult);
          continue;
        }

        if (evt.event === "error" && payload && typeof payload === "object") {
          const err = payload as {
            error_code?: string | null;
            message?: string;
            search_url?: string | null;
          };
          const message = err.message?.trim() || "爬虫搜品失败";
          handlers.onError?.({
            error_code: err.error_code,
            message,
            search_url: err.search_url,
          });
          fatal = new Error(message);
          continue;
        }
      }
    }
  }

  if (fatal) throw fatal;
  if (finalResult) return finalResult;

  // 兜底：无 result 时给空成功壳（不应常见）
  return {
    task_id: `crawl-${request.platform}`,
    status: {
      state: "error",
      label: "失败",
      hint: "直播流未返回结果",
      badge_class: "bg-destructive/15 text-destructive",
    },
    items: [] as CrawlProductItem[],
    total: 0,
    search_url: null,
    error_code: "tool.failed",
    message: "直播流未返回结果",
  };
}

export type { CrawlPlatform };
