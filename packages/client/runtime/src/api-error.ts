import { pushAppAlert } from "./app-alert";

export interface ApiErrorPayload {
  ok?: boolean;
  code?: string;
  message?: string;
}

export const SESSION_EXPIRED_CODE = "account.session_expired";

async function readApiError(response: Response): Promise<ApiErrorPayload> {
  try {
    return (await response.json()) as ApiErrorPayload;
  } catch {
    return { message: `请求失败（${response.status}）` };
  }
}

function isSessionExpiredPayload(payload: ApiErrorPayload): boolean {
  return payload.code === SESSION_EXPIRED_CODE;
}

/** 用应用内 Alert 展示错误，禁止 window.alert。 */
function showApiErrorMessage(payload: ApiErrorPayload, fallback = "请求失败") {
  const message = payload.message?.trim() || fallback;
  pushAppAlert({
    title: message,
    variant: "destructive",
  });
}

/**
 * 读取错误 payload 并按需弹 Alert，然后统一抛错（错误文案只在这里生成）。
 *
 * - silent=true：普通错误不弹窗（调用方自己处理），但会话过期仍要弹 ——
 *   那是全局必须看到的信号，不属于「调用方可处理」的范畴。
 * - 抛出的 Error 消息 = 后端 message || fallback，调用方 catch 后展示同一份文案。
 */
export async function handleApiResponseError(
  response: Response,
  fallback = "请求失败",
  { silent = false }: { silent?: boolean } = {},
): Promise<never> {
  const payload = await readApiError(response);
  if (isSessionExpiredPayload(payload) || !silent) {
    showApiErrorMessage(
      payload,
      isSessionExpiredPayload(payload) ? "登录已过期，请重新扫码登录" : fallback,
    );
  }
  throw new Error(payload.message?.trim() || fallback);
}
