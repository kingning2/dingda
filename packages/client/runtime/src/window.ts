/**
 * 桌面窗口 API 封装（v2 壳层唯一允许使用 @tauri-apps/api/window 的入口）。
 *
 * 提供最小化、最大化、关闭、拖拽与平台检测。
 */

import { getCurrentWindow } from "@tauri-apps/api/window";

export type DesktopPlatform = "macos" | "windows" | "linux";

declare global {
  interface Window {
    /** 由 Rust `append_invoke_initialization_script` 注入。 */
    __DINGDA_PLATFORM__?: DesktopPlatform;
  }
}

export function getPlatform(): DesktopPlatform {
  if (typeof window === "undefined") {
    return "windows";
  }
  const injected = window.__DINGDA_PLATFORM__;
  if (injected === "macos" || injected === "windows" || injected === "linux") {
    return injected;
  }
  return "windows";
}

export async function subscribeWindowMaximized(
  onChange: (maximized: boolean) => void,
): Promise<() => void> {
  const window = getCurrentWindow();
  onChange(await window.isMaximized());
  return window.onResized(async () => {
    onChange(await window.isMaximized());
  });
}

export async function minimizeWindow(): Promise<void> {
  await getCurrentWindow().minimize();
}

export async function toggleMaximizeWindow(): Promise<void> {
  const window = getCurrentWindow();
  if (await window.isMaximized()) {
    await window.unmaximize();
    return;
  }
  await window.maximize();
}

export async function closeWindow(): Promise<void> {
  await getCurrentWindow().close();
}

export async function startWindowDrag(): Promise<void> {
  await getCurrentWindow().startDragging();
}
