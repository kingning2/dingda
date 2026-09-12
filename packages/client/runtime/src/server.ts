/**
 * Python Server 连接状态。
 *
 * Web：默认连本机 Server（主开发路径）。
 * 桌面：由 Tauri 注入起停事件与 apiBaseUrl。
 */

import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { getHostCapabilities } from "./capabilities";
import { api, DEFAULT_WEB_API_BASE } from "./http-client";

export type ServerPhase = "offline" | "starting" | "ready" | "error";

export interface ServerStatus {
  phase: ServerPhase;
  ready: boolean;
  apiBaseUrl: string | null;
  error: string | null;
}

interface ServerStatusPayload {
  ready: boolean;
  apiBaseUrl: string;
}

const OFFLINE: ServerStatus = {
  phase: "offline",
  ready: false,
  apiBaseUrl: null,
  error: null,
};

const WEB_DEFAULT: ServerStatus = {
  phase: "ready",
  ready: true,
  apiBaseUrl: DEFAULT_WEB_API_BASE,
  error: null,
};

export function getInitialServerStatus(): ServerStatus {
  if (getHostCapabilities().desktop) {
    return { phase: "starting", ready: false, apiBaseUrl: null, error: null };
  }
  return WEB_DEFAULT;
}

export async function fetchServerStatus(): Promise<ServerStatus> {
  if (!getHostCapabilities().desktop) return WEB_DEFAULT;

  try {
    const payload = await invoke<ServerStatusPayload>("get_server_status");
    return {
      phase: payload.ready ? "ready" : "starting",
      ready: payload.ready,
      apiBaseUrl: payload.apiBaseUrl,
      error: null,
    };
  } catch {
    return { phase: "error", ready: false, apiBaseUrl: null, error: "无法读取 Server 状态" };
  }
}

/** Server 就绪后触发渐进预热，失败静默。 */
export async function kickServerWarmup(): Promise<void> {
  try {
    await api.get("/v1/bootstrap", { skipErrorToast: true, fallbackError: "bootstrap 失败" });
  } catch {
    // 预热失败不阻塞 UI
  }
}

export async function subscribeServerEvents(
  onChange: (status: ServerStatus) => void,
): Promise<() => void> {
  if (!isTauri()) return () => {};

  const unsubs: Array<() => void> = [];

  unsubs.push(
    await listen<string>("server-starting", (event) => {
      onChange({
        phase: "starting",
        ready: false,
        apiBaseUrl: event.payload,
        error: null,
      });
    }),
  );

  unsubs.push(
    await listen<string>("server-ready", (event) => {
      onChange({
        phase: "ready",
        ready: true,
        apiBaseUrl: event.payload,
        error: null,
      });
    }),
  );

  unsubs.push(
    await listen<string>("server-error", (event) => {
      onChange({
        phase: "error",
        ready: false,
        apiBaseUrl: null,
        error: event.payload,
      });
    }),
  );

  unsubs.push(
    await listen("server-stopped", () => {
      onChange(OFFLINE);
    }),
  );

  return () => {
    for (const unsub of unsubs) unsub();
  };
}
