import type {
  AccountPlatform,
  AccountQrCheckResponse,
  AccountQrStartResponse,
} from "@/contracts/account";

const QR_START_TIMEOUT_MS = 90_000;

interface ApiErrorPayload {
  ok?: boolean;
  message?: string;
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as ApiErrorPayload;
    return payload.message?.trim() || `请求失败（${response.status}）`;
  } catch {
    return `请求失败（${response.status}）`;
  }
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`请求超时（${Math.round(timeoutMs / 1000)}s），请确认 Camoufox 已安装且后端日志无报错`);
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function startAccountQrLogin(
  apiBaseUrl: string,
  platform: AccountPlatform,
): Promise<AccountQrStartResponse> {
  const response = await fetchWithTimeout(
    `${apiBaseUrl}/v1/channel/qr/start`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform }),
    },
    QR_START_TIMEOUT_MS,
  );

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return (await response.json()) as AccountQrStartResponse;
}

export async function checkAccountQrLogin(
  apiBaseUrl: string,
  sessionId: string,
): Promise<AccountQrCheckResponse> {
  const url = new URL(`${apiBaseUrl}/v1/channel/qr/check`);
  url.searchParams.set("session_id", sessionId);

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return (await response.json()) as AccountQrCheckResponse;
}
