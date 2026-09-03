/**
 * 后端连接状态 — 与 Tauri 壳层并行启动，不阻塞 UI 渲染。
 */

import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export type BackendPhase = "offline" | "starting" | "ready" | "error";

export interface BackendStatus {
  phase: BackendPhase;
  ready: boolean;
  apiBaseUrl: string | null;
  error: string | null;
}

interface BackendStatusPayload {
  ready: boolean;
  apiBaseUrl: string;
}

const OFFLINE: BackendStatus = {
  phase: "offline",
  ready: false,
  apiBaseUrl: null,
  error: null,
};

export function getInitialBackendStatus(): BackendStatus {
  return isTauri()
    ? { phase: "starting", ready: false, apiBaseUrl: null, error: null }
    : OFFLINE;
}

export async function fetchBackendStatus(): Promise<BackendStatus> {
  if (!isTauri()) return OFFLINE;

  try {
    const payload = await invoke<BackendStatusPayload>("get_backend_status");
    return {
      phase: payload.ready ? "ready" : "starting",
      ready: payload.ready,
      apiBaseUrl: payload.apiBaseUrl,
      error: null,
    };
  } catch {
    return { phase: "error", ready: false, apiBaseUrl: null, error: "无法读取后端状态" };
  }
}

/** 后端就绪后触发渐进预热，失败静默（页面仍可用 mock）。 */
export async function kickBackendWarmup(apiBaseUrl: string): Promise<void> {
  try {
    await fetch(`${apiBaseUrl}/v1/bootstrap`, { method: "GET" });
  } catch {
    // 预热失败不阻塞 UI
  }
}

export async function subscribeBackendEvents(
  onChange: (status: BackendStatus) => void,
): Promise<() => void> {
  if (!isTauri()) return () => {};

  const unsubs: Array<() => void> = [];

  unsubs.push(
    await listen<string>("backend-starting", (event) => {
      onChange({
        phase: "starting",
        ready: false,
        apiBaseUrl: event.payload,
        error: null,
      });
    }),
  );

  unsubs.push(
    await listen<string>("backend-ready", (event) => {
      onChange({
        phase: "ready",
        ready: true,
        apiBaseUrl: event.payload,
        error: null,
      });
    }),
  );

  unsubs.push(
    await listen<string>("backend-error", (event) => {
      onChange({
        phase: "error",
        ready: false,
        apiBaseUrl: null,
        error: event.payload,
      });
    }),
  );

  unsubs.push(
    await listen("backend-stopped", () => {
      onChange(OFFLINE);
    }),
  );

  return () => {
    for (const unsub of unsubs) unsub();
  };
}
