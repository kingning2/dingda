/**
 * 错误生命周期：全局 reporter、后端不可用状态、壳层安装钩子。
 *
 * 职责：
 * - 安装全局错误 reporter（invoke.ts 的 IPC 错误经此上报）
 * - 监听 window error / unhandledrejection → 代码错误（仅日志）
 * - 订阅后端 runtime/error / sidecar.restarted 事件 → 网络错误标记
 * - 网络 / IPC 错误：toast + 日志；网络错误额外标记后端不可用；代码错误：仅日志
 *
 * 模块级 `installed` 守卫保证 StrictMode 下只安装一次，且不随组件卸载拆除
 * （全局单例）。
 *
 * @author Xiaoman
 * @created 2026-08-18
 */

import { useEffect } from "react";

import {
  IpcError,
  setErrorReporter,
  stringifyError,
  type DeskError,
} from "@desk/platform/error";
import { listenRuntimeError, listenSidecarRestarted } from "@desk/platform/events";
import { logWrite } from "@desk/platform/ipc/log";
import { toast } from "@desk/ui";
import { createDeskStore } from "@desk/store";

export interface ErrorState {
  /** 后端是否不可用。 */
  backendUnavailable: boolean;
  /** 标记后端不可用状态。 */
  setBackendUnavailable: (value: boolean) => void;
}

export const useErrorStore = createDeskStore<ErrorState>((set) => ({
  backendUnavailable: false,
  setBackendUnavailable: (value) => set({ backendUnavailable: value }),
}));

/** 日志通道自身的命令：失败不上报，防自反馈循环。 */
const SELF_FEEDBACK_COMMANDS = new Set(["log_write", "log_recent", "log_clear"]);

/** 稳定 toast id — 同分类反复触发只更新同一条，避免刷屏。 */
const TOAST_IDS: Record<string, string> = {
  network: "error-network",
  ipc: "error-ipc",
};

/** 已上报的错误实例（防 IPC 错误被 invoke 上报后再次经 unhandledrejection 重复上报）。 */
const reportedErrors = new WeakSet<object>();

let installed = false;

/**
 * 统一错误处理：分类分流 → 日志 / toast / 状态标记。
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @param error - 已分类的错误
 */
function handleError(error: DeskError): void {
  if (SELF_FEEDBACK_COMMANDS.has(error.command ?? "")) {
    return;
  }
  if (error !== null && typeof error === "object") {
    if (reportedErrors.has(error)) {
      return;
    }
    reportedErrors.add(error);
  }
  try {
    const prefix = error.kind === "code" ? "[error:code]" : `[${error.kind}]`;
    void logWrite(`${prefix} ${error.message}`, "ERROR").catch(() => {});
    if (error.kind === "code") {
      return;
    }
    toast.error(error.message, { id: TOAST_IDS[error.kind] ?? undefined });
    if (error.kind === "network") {
      useErrorStore.getState().setBackendUnavailable(true);
    }
  } catch {
    // 上报自身出错不中断。
  }
}

/**
 * 将未捕获异常包装为 DeskError — IPC 错误保持原分类，其余强制 code。
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @param error - window error 或 unhandledrejection 的原因
 * @returns DeskError
 */
function wrapUncaught(error: unknown): DeskError {
  if (error instanceof IpcError) {
    return error;
  }
  return { kind: "code", message: stringifyError(error) };
}

/**
 * 安装全局错误处理（幂等）。
 *
 * @author Xiaoman
 * @created 2026-08-18
 */
function install(): void {
  if (installed) {
    return;
  }
  installed = true;

  setErrorReporter(handleError);

  window.addEventListener("error", (event) => {
    handleError(wrapUncaught(event.error ?? event.message));
  });
  window.addEventListener("unhandledrejection", (event) => {
    handleError(wrapUncaught(event.reason));
  });

  void listenRuntimeError((payload) => {
    handleError({ kind: "network", message: payload.message });
  }).catch(() => {});
  void listenSidecarRestarted(() => {
    useErrorStore.getState().setBackendUnavailable(false);
  }).catch(() => {});
}

/**
 * 错误生命周期钩子 — 应用根挂载一次。
 *
 * @author Xiaoman
 * @created 2026-08-18
 */
export function useErrorLifecycle(): void {
  useEffect(() => {
    install();
  }, []);
}
