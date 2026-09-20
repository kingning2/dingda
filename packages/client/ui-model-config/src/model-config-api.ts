/**
 * 模型配置 HTTP API。
 *
 * 职责：
 *     把 `/v1/llm` 的端点包成类型化函数；只发请求与解包，不管状态也不弹提示。
 *
 * 设计说明：
 *     - 统一走 `@v2/runtime/http-client`，不自建 fetch
 *     - `skipErrorToast: true`：提示交给调用方。探活失败与拉模型列表失败本身都是
 *       **200 + `ok=false`**，不是异常；若让它走默认拦截，用户会同时看到错误弹窗和
 *       一份结果，两条路径说同一件事
 *     - 改凭据时 `body` 里**只放要改的字段**。后端按「字段在不在请求体里」判断改不改，
 *       所以 `base_url: undefined` 与 `base_url: null` 的差别必须由调用方明确表达：
 *       前者是「不改」，后者是「恢复供应商默认地址」
 */

import type {
  LlmCheckResponse,
  LlmCheckView,
  LlmCredentialCreateBody,
  LlmCredentialItem,
  LlmCredentialListResponse,
  LlmCredentialResponse,
  LlmCredentialUpdateBody,
  LlmImportEnvResponse,
  LlmModelListBody,
  LlmModelListResponse,
  LlmProviderItem,
  LlmProviderListResponse,
} from "@v2/contracts/model";
import { api } from "@v2/runtime/http-client";

const BASE = "/v1/llm";

/**
 * 拉模型列表的超时。
 *
 * 后端自己 20 秒就放弃（`PROBE_TIMEOUT_S`），这里留 10 秒余量：先于前端超时，
 * 用户才能看到「上游超时」而不是一句「请求超时」。
 */
const MODELS_TIMEOUT_MS = 30_000;

/** 可选供应商目录。 */
export async function listLlmProviders(options?: { signal?: AbortSignal }): Promise<LlmProviderItem[]> {
  const { data } = await api.get<LlmProviderListResponse>(`${BASE}/providers`, {
    signal: options?.signal,
    fallbackError: "加载模型供应商失败",
    skipErrorToast: true,
  });
  return data.items;
}

/** 全部凭据 + 当前使用中的 id。 */
export async function listLlmCredentials(options?: {
  signal?: AbortSignal;
}): Promise<LlmCredentialListResponse> {
  const { data } = await api.get<LlmCredentialListResponse>(`${BASE}/credentials`, {
    signal: options?.signal,
    fallbackError: "加载模型凭据失败",
    skipErrorToast: true,
  });
  return data;
}

/** 新建一条凭据。 */
export async function createLlmCredential(body: LlmCredentialCreateBody): Promise<LlmCredentialItem> {
  const { data } = await api.post<LlmCredentialResponse>(`${BASE}/credentials`, body, {
    timeoutMs: 15_000,
    fallbackError: "新增模型凭据失败",
    skipErrorToast: true,
  });
  return data.item;
}

/** 改一条凭据；`body` 里只放要改的字段。 */
export async function updateLlmCredential(
  credentialId: string,
  body: LlmCredentialUpdateBody,
): Promise<LlmCredentialItem> {
  const { data } = await api.put<LlmCredentialResponse>(
    `${BASE}/credentials/${encodeURIComponent(credentialId)}`,
    body,
    { timeoutMs: 15_000, fallbackError: "保存模型凭据失败", skipErrorToast: true },
  );
  return data.item;
}

/** 删一条凭据。 */
export async function deleteLlmCredential(credentialId: string): Promise<void> {
  await api.delete(`${BASE}/credentials/${encodeURIComponent(credentialId)}`, {
    fallbackError: "删除模型凭据失败",
    skipErrorToast: true,
  });
}

/** 把某条设为唯一使用中。 */
export async function activateLlmCredential(credentialId: string): Promise<LlmCredentialItem> {
  const { data } = await api.post<LlmCredentialResponse>(
    `${BASE}/credentials/${encodeURIComponent(credentialId)}/activate`,
    undefined,
    { fallbackError: "切换模型凭据失败", skipErrorToast: true },
  );
  return data.item;
}

/**
 * 发一次最小请求验连通性。
 *
 * 失败也回 200，结果在 `check.ok` 里 —— 调用方按业务结果处理，不要包在 try 里当异常。
 */
export async function testLlmCredential(
  credentialId: string,
  options?: { signal?: AbortSignal },
): Promise<LlmCheckView> {
  const { data } = await api.post<LlmCheckResponse>(
    `${BASE}/credentials/${encodeURIComponent(credentialId)}/test`,
    undefined,
    {
      signal: options?.signal,
      timeoutMs: 30_000,
      fallbackError: "模型连通性检测失败",
      skipErrorToast: true,
    },
  );
  return data.check;
}

/** 把 `.env` / 真实环境里那份配置收编成一条凭据（查重，重复点不会攒条目）。 */
export async function importLlmCredentialFromEnv(): Promise<LlmImportEnvResponse> {
  const { data } = await api.post<LlmImportEnvResponse>(`${BASE}/credentials/import-env`, undefined, {
    timeoutMs: 15_000,
    fallbackError: "从环境变量导入失败",
    skipErrorToast: true,
  });
  return data;
}

/**
 * 用**还没保存**的连接参数拉可用模型。
 *
 * 表单里刚粘上 key 就能拉，不必先存一条废凭据再删。
 *
 * 拉不到也回 200，结果在 `ok` / `message` 里 —— 调用方按业务结果处理，不要包在 try 里当异常。
 */
export async function listLlmModelsForDraft(
  body: LlmModelListBody,
  options?: { signal?: AbortSignal },
): Promise<LlmModelListResponse> {
  const { data } = await api.post<LlmModelListResponse>(`${BASE}/models`, body, {
    signal: options?.signal,
    timeoutMs: MODELS_TIMEOUT_MS,
    fallbackError: "获取可用模型失败",
    skipErrorToast: true,
  });
  return data;
}

/**
 * 用**已保存凭据**的 key 拉可用模型。
 *
 * 编辑态必须走这条：key 只回掩码，浏览器里根本没有原文。
 */
export async function listLlmCredentialModels(
  credentialId: string,
  options?: { signal?: AbortSignal },
): Promise<LlmModelListResponse> {
  const { data } = await api.get<LlmModelListResponse>(
    `${BASE}/credentials/${encodeURIComponent(credentialId)}/models`,
    {
      signal: options?.signal,
      timeoutMs: MODELS_TIMEOUT_MS,
      fallbackError: "获取可用模型失败",
      skipErrorToast: true,
    },
  );
  return data;
}
