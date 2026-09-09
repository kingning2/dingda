import { pushAppAlert } from "@/lib/app-alert";

export interface ApiErrorPayload {
  ok?: boolean;
  code?: string;
  message?: string;
}

export const SESSION_EXPIRED_CODE = "account.session_expired";

export async function readApiError(response: Response): Promise<ApiErrorPayload> {
  try {
    return (await response.json()) as ApiErrorPayload;
  } catch {
    return { message: `请求失败（${response.status}）` };
  }
}

export function isSessionExpiredPayload(payload: ApiErrorPayload): boolean {
  return payload.code === SESSION_EXPIRED_CODE;
}

/** 用应用内 Alert 展示错误，禁止 window.alert。 */
export function showApiErrorMessage(payload: ApiErrorPayload, fallback = "请求失败") {
  const message = payload.message?.trim() || fallback;
  pushAppAlert({
    title: message,
    variant: "destructive",
  });
}

export async function handleApiResponseError(
  response: Response,
  fallback = "请求失败",
): Promise<never> {
  const payload = await readApiError(response);
  if (isSessionExpiredPayload(payload)) {
    showApiErrorMessage(payload, "登录已过期，请重新扫码登录");
  } else {
    showApiErrorMessage(payload, fallback);
  }
  throw new Error(payload.message?.trim() || fallback);
}
