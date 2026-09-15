/**
 * 桌面 E2E 的端口与健康检查辅助。
 *
 * 这些检查跑在 **测试进程（Node）** 里，不是 WebView 上下文 —— 目的是从外部
 * 独立验证壳层的行为，而不是相信前端自报的状态。
 */
import net from "node:net";

/** 探测某端口是否有监听者。连接成功即视为有。 */
export function isPortListening(port: number, host = "127.0.0.1"): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = net.connect({ port, host });

    const settle = (result: boolean) => {
      socket.removeAllListeners();
      socket.destroy();
      resolve(result);
    };

    socket.setTimeout(1_000);
    socket.once("connect", () => settle(true));
    socket.once("error", () => settle(false));
    socket.once("timeout", () => settle(false));
  });
}

/** 轮询等待端口进入监听，超时返回 false。 */
export async function waitForPort(
  port: number,
  timeoutMs = 30_000,
  host = "127.0.0.1",
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await isPortListening(port, host)) return true;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  return false;
}

export type HealthPayload = { status: string; phase: string };

/**
 * 直接打 Server 的 `/health`。
 *
 * 注意 `/health` **不会触发完整预热**（见 `packages-py/api/src/api/health.py`），
 * 它只回报当前阶段，所以这里断言的是存活而非就绪。
 */
export async function fetchHealth(
  port: number,
  timeoutMs = 5_000,
): Promise<HealthPayload | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`http://127.0.0.1:${port}/health`, {
      signal: controller.signal,
    });
    if (!response.ok) return null;
    return (await response.json()) as HealthPayload;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
