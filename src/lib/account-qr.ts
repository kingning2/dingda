import type {
  AccountPlatform,
  AccountQrCheckResponse,
  AccountQrStartResponse,
} from "@v2/contracts/account";
import { api } from "@/lib/http-client";

const QR_START_TIMEOUT_MS = 90_000;

export async function startAccountQrLogin(
  platform: AccountPlatform,
): Promise<AccountQrStartResponse> {
  try {
    const { data } = await api.post<AccountQrStartResponse>(
      "/v1/channel/qr/start",
      { platform },
      {
        timeoutMs: QR_START_TIMEOUT_MS,
        skipErrorToast: true,
        fallbackError: "启动扫码失败",
      },
    );
    return data;
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("请求超时")) {
      throw new Error(
        `请求超时（${Math.round(QR_START_TIMEOUT_MS / 1000)}s），请确认 Camoufox 已安装且后端日志无报错`,
      );
    }
    throw error;
  }
}

export async function checkAccountQrLogin(
  sessionId: string,
): Promise<AccountQrCheckResponse> {
  const { data } = await api.get<AccountQrCheckResponse>("/v1/channel/qr/check", {
    query: { session_id: sessionId },
    skipErrorToast: true,
    fallbackError: "轮询扫码状态失败",
  });
  return data;
}

/** 关闭扫码弹窗时通知后端打断浏览器任务（幂等）。 */
export async function cancelAccountQrLogin(sessionId: string): Promise<void> {
  try {
    await api.post(
      "/v1/channel/qr/cancel",
      { session_id: sessionId },
      {
        skipErrorToast: true,
        keepalive: true,
        fallbackError: "取消扫码失败",
        timeoutMs: 5_000,
      },
    );
  } catch {
    // 关窗场景：后端已结束或网络抖动都不挡关闭
  }
}
