/**
 * AI 配置 IPC 封装。
 *
 * @author Xiaoman
 * @created 2026-08-13
 */

import type {
  AiIpcConfigRequest,
  AiIpcConfigResponse,
  AiIpcListModelsResponse,
  AiIpcProvidersCatalogResponse,
} from "@desk/contracts";

import { call } from "./invoke";

/**
 * 读取 AI provider 配置。
 *
 * @author Xiaoman
 * @created 2026-08-13
 *
 * @returns 当前 AI 配置
 */
export function aiConfigGet(): Promise<AiIpcConfigResponse> {
  return call<AiIpcConfigResponse>("ai_config_get");
}

/**
 * 写入 AI provider 配置。
 *
 * @author Xiaoman
 * @created 2026-08-13
 *
 * @param config - 新配置
 * @returns 写入后的配置
 */
export function aiConfigSet(config: AiIpcConfigRequest): Promise<AiIpcConfigResponse> {
  return call<AiIpcConfigResponse>("ai_config_set", { config });
}

/**
 * LangGraph 可直连的平台目录（只读）。
 */
export function aiProvidersCatalog(): Promise<AiIpcProvidersCatalogResponse> {
  return call<AiIpcProvidersCatalogResponse>("ai_providers_catalog");
}

/**
 * 拉取平台可用模型列表（填 API Key 后调用）。
 */
export function aiListModels(
  baseUrl: string,
  apiKey: string,
  kind?: string,
): Promise<AiIpcListModelsResponse> {
  return call<AiIpcListModelsResponse>("ai_list_models", { baseUrl, apiKey, kind });
}

/**
 * API Key 连通性探测结果。
 *
 * @author Xiaoman
 * @created 2026-08-13
 */
export interface AiApiKeyTestResult {
  /** 是否探测成功。 */
  ok: boolean;
  /** 结果说明。 */
  message: string;
}

/**
 * 单币种余额条目（与 Rust `AiBalanceInfoDto` 对齐）。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */
export interface AiBalanceInfoDto {
  /** 币种（CNY / USD）。 */
  currency: string;
  /** 总可用余额。 */
  total_balance: string;
  /** 赠金余额。 */
  granted_balance: string;
  /** 充值余额。 */
  topped_up_balance: string;
}

/**
 * 账号余额查询结果。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */
export interface AiAccountBalanceResult {
  /** 是否查询成功。 */
  ok: boolean;
  /** 余额是否足够调用 API。 */
  is_available: boolean;
  /** 各币种余额。 */
  balances: AiBalanceInfoDto[];
  /** 失败时的可读说明。 */
  message: string;
}

/**
 * 探测 OpenAI 兼容 API Key。
 *
 * @author Xiaoman
 * @created 2026-08-13
 *
 * @param baseUrl - provider base URL
 * @param apiKey - API Key
 * @param kind - 平台类型；deepseek 走余额接口，豆包等走 `/models`
 * @returns 探测结果
 */
export function aiTestApiKey(
  baseUrl: string,
  apiKey: string,
  kind?: string,
): Promise<AiApiKeyTestResult> {
  return call<AiApiKeyTestResult>("ai_test_api_key", { baseUrl, apiKey, kind });
}

/**
 * 查询账号余额。
 *
 * @author Xiaoman
 * @created 2026-08-20
 *
 * @param baseUrl - provider base URL
 * @param apiKey - API Key
 * @returns 余额结果
 */
export function aiAccountBalance(
  baseUrl: string,
  apiKey: string,
): Promise<AiAccountBalanceResult> {
  return call<AiAccountBalanceResult>("ai_account_balance", { baseUrl, apiKey });
}
