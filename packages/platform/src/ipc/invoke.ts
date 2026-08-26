/**
 * 带耗时日志的 Tauri IPC 调用封装。
 *
 * 负责：
 * - 统一 React → Rust `invoke` 入口
 * - 记录调用中文名 / durationMs / 成败（经 console-bridge 进入日志面板）
 * - 对高频命令降噪
 *
 * @author Xiaoman
 * @created 2026-08-13
 */

import { invoke as tauriInvoke } from "@tauri-apps/api/core";

import {
  classifyError,
  IpcError,
  reportError,
  stringifyError,
  type ErrorKind,
} from "../error";

import { ipcCommandLabel } from "./ipc-command-labels";

/**
 * IPC 统一响应体（仿 HTTP 风格）。
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @typeParam T - 业务数据类型
 */
export interface IpcResponse<T> {
  /** 业务状态码（成功固定 200）。 */
  code: number;
  /** 响应消息。 */
  message: string;
  /** 业务数据。 */
  data: T;
}

/** 完全静默：日志面板自身轮询，再打日志会自反馈刷屏。 */
const SILENT_COMMANDS = new Set(["log_recent", "log_clear", "log_write"]);

/** 高频探测/轮询命令：正常且够快时只打 debug。 */
const QUIET_COMMANDS = new Set([
  "agent_ping",
  "agent_run_status",
  "agent_run_get",
  "channel_qr_check",
  "license_status",
]);

const QUIET_SLOW_MS = 500;

/**
 * 调用 Tauri command，并输出耗时日志。
 *
 * @author Xiaoman
 * @created 2026-08-13
 *
 * @typeParam T - 响应类型
 * @param command - Tauri command 名
 * @param payload - 可选参数对象
 * @returns command 返回值
 */
export async function call<T>(
  command: string,
  payload?: Record<string, unknown>,
): Promise<T> {
  const started = performance.now();
  try {
    const result = await tauriInvoke<T | IpcResponse<T>>(command, payload);
    const durationMs = Math.max(0, Math.round(performance.now() - started));
    if (!SILENT_COMMANDS.has(command)) {
      logIpcCompleted(command, durationMs, true);
    }
    if (isIpcResponse<T>(result)) {
      if (result.code !== 200) {
        const ipcError = new IpcError({
          kind: classifyResponseCode(result.code),
          command,
          code: result.code,
          message: result.message,
        });
        logIpcCompleted(command, durationMs, false, ipcError);
        reportError(ipcError, command);
        throw ipcError;
      }
      return result.data;
    }
    return result;
  } catch (error) {
    const durationMs = Math.max(0, Math.round(performance.now() - started));
    // 静默命令失败仍要可见，否则面板拉取异常无从排查。
    logIpcCompleted(command, durationMs, false, error);
    const ipcError = wrapIpcError(error, command);
    reportError(ipcError, command);
    throw ipcError;
  }
}

/**
 * 调用 Tauri command，并返回统一响应结构。
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @typeParam T - 响应 data 类型
 * @param command - Tauri command 名
 * @param payload - 可选参数对象
 * @returns `{ code, message, data }` 响应
 */
export async function callRequest<T>(
  command: string,
  payload?: Record<string, unknown>,
): Promise<IpcResponse<T>> {
  const started = performance.now();
  try {
    const result = await tauriInvoke<IpcResponse<T>>(command, payload);
    const durationMs = Math.max(0, Math.round(performance.now() - started));
    if (!SILENT_COMMANDS.has(command)) {
      logIpcCompleted(command, durationMs, true);
    }
    return result;
  } catch (error) {
    const durationMs = Math.max(0, Math.round(performance.now() - started));
    logIpcCompleted(command, durationMs, false, error);
    const ipcError = wrapIpcError(error, command);
    reportError(ipcError, command);
    throw ipcError;
  }
}

/**
 * 将任意 invoke 拒绝错误包装为 IpcError（保留 command 上下文）。
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @param error - invoke 拒绝的原始错误
 * @param command - Tauri command 名
 * @returns 带分类与 command 的 IpcError
 */
function wrapIpcError(error: unknown, command: string): IpcError {
  if (error instanceof IpcError) {
    return error;
  }
  const classified = classifyError(error, command);
  return new IpcError({
    kind: classified.kind,
    message: classified.message,
    command,
    cause: error,
  });
}

/**
 * 按业务状态码判定错误分类 — 5xx 视为后端不可用（网络错误）。
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @param code - 业务状态码
 * @returns 错误分类
 */
function classifyResponseCode(code: number): ErrorKind {
  return code >= 500 ? "network" : "ipc";
}

/**
 * 输出 IPC 完成日志（成功 INFO/DEBUG，失败 WARN）。
 *
 * @author Xiaoman
 * @created 2026-08-13
 *
 * @param command - command 名
 * @param durationMs - 耗时毫秒
 * @param ok - 是否成功
 * @param error - 失败时的错误
 */
function logIpcCompleted(
  command: string,
  durationMs: number,
  ok: boolean,
  error?: unknown,
): void {
  const label = ipcCommandLabel(command);
  const message = ok
    ? `IPC 调用完成 command=${label} durationMs=${durationMs}`
    : `IPC 调用失败 command=${label} durationMs=${durationMs} error=${stringifyError(error)}`;

  if (!ok) {
    console.warn(message);
    return;
  }

  const quiet = QUIET_COMMANDS.has(command) && durationMs < QUIET_SLOW_MS;
  if (quiet) {
    console.debug(message);
  } else {
    console.info(message);
  }
}

/**
 * 判断对象是否为统一响应结构。
 *
 * @author Xiaoman
 * @created 2026-08-18
 *
 * @typeParam T - data 类型
 * @param value - 待判断值
 * @returns 命中统一响应体结构返回 true
 */
function isIpcResponse<T>(value: unknown): value is IpcResponse<T> {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.code === "number" &&
    typeof candidate.message === "string" &&
    Object.prototype.hasOwnProperty.call(candidate, "data")
  );
}
