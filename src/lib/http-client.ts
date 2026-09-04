/**
 * Python Server HTTP 客户端。
 *
 * 职责：统一拼 baseUrl、JSON、请求/响应拦截与错误处理。
 * 业务模块只调 api.get/put/...，不要各自 fetch。
 */

import {
  handleApiResponseError,
  readApiError,
  showApiErrorMessage,
  isSessionExpiredPayload,
} from "@/lib/api-error";
import { getHostCapabilities } from "@/lib/capabilities";

/** Web 默认 API；桌面由 ServerProvider 注入。 */
export const DEFAULT_WEB_API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ||
  "http://127.0.0.1:8787";

let apiBaseUrl: string | null = getHostCapabilities().desktop
  ? null
  : DEFAULT_WEB_API_BASE;

export type ApiRequestContext = {
  url: string;
  init: RequestInit;
  fallbackError: string;
  allowStatuses: number[];
  skipErrorToast: boolean;
};

export type ApiResponseContext = {
  response: Response;
  request: ApiRequestContext;
};

type RequestInterceptor = (
  ctx: ApiRequestContext,
) => ApiRequestContext | Promise<ApiRequestContext>;

type ResponseInterceptor = (
  ctx: ApiResponseContext,
) => ApiResponseContext | Promise<ApiResponseContext>;

const requestInterceptors: RequestInterceptor[] = [];
const responseInterceptors: ResponseInterceptor[] = [];

/** Server 就绪后注入 baseUrl（桌面由 ServerProvider 调用）。 */
export function setApiBaseUrl(url: string | null): void {
  apiBaseUrl = url?.trim() || null;
}

export function getApiBaseUrl(): string | null {
  return apiBaseUrl;
}

export function onApiRequest(interceptor: RequestInterceptor): () => void {
  requestInterceptors.push(interceptor);
  return () => {
    const index = requestInterceptors.indexOf(interceptor);
    if (index >= 0) requestInterceptors.splice(index, 1);
  };
}

export function onApiResponse(interceptor: ResponseInterceptor): () => void {
  responseInterceptors.push(interceptor);
  return () => {
    const index = responseInterceptors.indexOf(interceptor);
    if (index >= 0) responseInterceptors.splice(index, 1);
  };
}

function resolveBaseUrl(override?: string | null): string {
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
  /** 超时毫秒；超时抛 Error（不走响应拦截） */
  timeoutMs?: number;
  fallbackError?: string;
  /** 这些状态码不当错误抛出（如 404） */
  allowStatuses?: number[];
  /** 不弹窗，仍抛 Error */
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

async function runRequestInterceptors(ctx: ApiRequestContext): Promise<ApiRequestContext> {
  let current = ctx;
  for (const interceptor of requestInterceptors) {
    current = await interceptor(current);
  }
  return current;
}

async function runResponseInterceptors(ctx: ApiResponseContext): Promise<ApiResponseContext> {
  let current = ctx;
  for (const interceptor of responseInterceptors) {
    current = await interceptor(current);
  }
  return current;
}

async function defaultResponseGuard(ctx: ApiResponseContext): Promise<ApiResponseContext> {
  const { response, request } = ctx;
  if (response.ok || request.allowStatuses.includes(response.status)) {
    return ctx;
  }

  if (request.skipErrorToast) {
    const payload = await readApiError(response);
    if (isSessionExpiredPayload(payload)) {
      showApiErrorMessage(payload, "登录已过期，请重新扫码登录");
    }
    throw new Error(payload.message?.trim() || request.fallbackError);
  }

  await handleApiResponseError(response, request.fallbackError);
  return ctx;
}

// 内置响应拦截：统一错误处理
onApiResponse(defaultResponseGuard);

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

  let ctx: ApiRequestContext = {
    url: withQuery(joinUrl(base, path), options.query),
    init: {
      method,
      headers,
      body: rawBody,
      signal,
      keepalive: options.keepalive ?? false,
    },
    fallbackError: options.fallbackError ?? "请求失败",
    allowStatuses: options.allowStatuses ?? [],
    skipErrorToast: options.skipErrorToast ?? false,
  };

  try {
    ctx = await runRequestInterceptors(ctx);
    let response: Response;
    try {
      response = await fetch(ctx.url, ctx.init);
    } catch (error) {
      if (timedOut) {
        throw new Error(
          `请求超时（${Math.round((options.timeoutMs ?? 0) / 1000)}s），请稍后重试`,
        );
      }
      throw error;
    }

    const guarded = await runResponseInterceptors({ response, request: ctx });

    if (guarded.response.status === 204) {
      return { data: undefined as T, response: guarded.response };
    }

    const text = await guarded.response.text();
    if (!text) {
      return { data: undefined as T, response: guarded.response };
    }

    try {
      return { data: JSON.parse(text) as T, response: guarded.response };
    } catch {
      return { data: text as T, response: guarded.response };
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
