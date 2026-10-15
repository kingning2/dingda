/**
 * Python Server HTTP 客户端。
 *
 * 职责：统一拼 baseUrl、JSON、超时与错误处理（默认弹 Alert，特殊场景 skipErrorToast）。
 * 业务模块只调 api.get/put/...，不要各自 fetch。
 */

import { handleApiResponseError } from "./api-error";
import { getHostCapabilities } from "./capabilities";

/** Web 默认 API；桌面由 ServerProvider 注入。 */
export const DEFAULT_WEB_API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ||
  "http://127.0.0.1:8787";

let apiBaseUrl: string | null = getHostCapabilities().desktop
  ? null
  : DEFAULT_WEB_API_BASE;

/** Server 就绪后注入 baseUrl（桌面由 ServerProvider 调用）。 */
export function setApiBaseUrl(url: string | null): void {
  apiBaseUrl = url?.trim() || null;
}

export function getApiBaseUrl(): string | null {
  return apiBaseUrl;
}

/**
 * 解析出可用的 base URL：优先用调用方给的覆盖值，否则用 `setApiBaseUrl` 注入的。
 * 都没有就抛错 —— 调用方不该在 Server 未就绪时发请求。
 *
 * 导出给需要自己发 `fetch` 的场景（如 SSE 流式：统一客户端会一次性读完响应，
 * 做不了流式）。
 */
export function resolveBaseUrl(override?: string | null): string {
  const base = (override ?? apiBaseUrl)?.trim();
  if (!base) {
    throw new Error("服务未就绪，无法发起请求");
  }
  return base.replace(/\/$/, "");
}

function joinUrl(base: string, path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalized}`;
}

export type ApiRequestOptions = {
  /** 覆盖当前注入的 baseUrl */
  baseUrl?: string | null;
  query?: Record<string, string | number | boolean | null | undefined>;
  headers?: HeadersInit;
  signal?: AbortSignal;
  /** 超时毫秒；超时抛 Error */
  timeoutMs?: number;
  /** 后端没给 message 时的兜底文案 */
  fallbackError?: string;
  /** 这些状态码不当错误抛出（如 404） */
  allowStatuses?: number[];
  /** 错误不弹窗（仍抛 Error）；会话过期除外 —— 那是全局信号 */
  skipErrorToast?: boolean;
  /** 页面卸载时仍尽量发完（Ctrl+R 落库） */
  keepalive?: boolean;
  rawBody?: BodyInit | null;
};

function withQuery(url: string, query?: ApiRequestOptions["query"]): string {
  if (!query) return url;
  const parsed = new URL(url);
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined) continue;
    parsed.searchParams.set(key, String(value));
  }
  return parsed.toString();
}

async function request<T>(
  method: string,
  path: string,
  body: unknown | undefined,
  options: ApiRequestOptions = {},
): Promise<{ data: T; response: Response }> {
  const base = resolveBaseUrl(options.baseUrl);
  const headers = new Headers(options.headers);
  let rawBody = options.rawBody ?? null;

  if (body !== undefined && rawBody == null) {
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    rawBody = JSON.stringify(body);
  }

  let signal = options.signal;
  let timeoutId: number | undefined;
  let timedOut = false;
  if (options.timeoutMs && options.timeoutMs > 0) {
    const controller = new AbortController();
    if (options.signal) {
      if (options.signal.aborted) {
        controller.abort();
      } else {
        options.signal.addEventListener("abort", () => controller.abort(), { once: true });
      }
    }
    timeoutId = window.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, options.timeoutMs);
    signal = controller.signal;
  }

  try {
    let response: Response;
    try {
      response = await fetch(withQuery(joinUrl(base, path), options.query), {
        method,
        headers,
        body: rawBody,
        signal,
        keepalive: options.keepalive ?? false,
      });
    } catch (error) {
      if (timedOut) {
        throw new Error(
          `请求超时（${Math.round((options.timeoutMs ?? 0) / 1000)}s），请稍后重试`,
        );
      }
      throw error;
    }

    if (!response.ok && !options.allowStatuses?.includes(response.status)) {
      await handleApiResponseError(response, options.fallbackError ?? "请求失败", {
        silent: options.skipErrorToast ?? false,
      });
    }

    if (response.status === 204) {
      return { data: undefined as T, response };
    }

    const text = await response.text();
    if (!text) {
      return { data: undefined as T, response };
    }

    try {
      return { data: JSON.parse(text) as T, response };
    } catch {
      // 非法 JSON 不能谎称是 T：直接把原文抛给调用方排查
      throw new Error(`响应不是 JSON：${text.slice(0, 120)}`);
    }
  } finally {
    if (timeoutId !== undefined) {
      window.clearTimeout(timeoutId);
    }
  }
}

/** 统一导出的请求入口。 */
export const api = {
  get<T>(path: string, options?: ApiRequestOptions) {
    return request<T>("GET", path, undefined, options);
  },
  post<T>(path: string, body?: unknown, options?: ApiRequestOptions) {
    return request<T>("POST", path, body, options);
  },
  put<T>(path: string, body?: unknown, options?: ApiRequestOptions) {
    return request<T>("PUT", path, body, options);
  },
  patch<T>(path: string, body?: unknown, options?: ApiRequestOptions) {
    return request<T>("PATCH", path, body, options);
  },
  delete<T>(path: string, options?: ApiRequestOptions) {
    return request<T>("DELETE", path, undefined, options);
  },
};
