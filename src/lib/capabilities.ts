/**
 * 宿主能力（boot facts）。
 *
 * 对齐 dsh 思路：Web 产品默认可用；桌面壳注入额外能力。
 * 不要用散落的 isTauri() 分支冒充能力系统，也不要为此拆 packages/。
 */

import { isTauri } from "@tauri-apps/api/core";

export type HostCapabilities = {
  /** 运行在 Tauri 壳内 */
  desktop: boolean;
  /** 外部 CLI Agent（Codex/Claude/…）— 仅客户端 */
  externalAgents: boolean;
  /** 原生窗口铬（标题栏拖拽等） */
  windowChrome: boolean;
};

export function getHostCapabilities(): HostCapabilities {
  const desktop = isTauri();
  return {
    desktop,
    externalAgents: desktop,
    windowChrome: desktop,
  };
}

export function supportsExternalAgents(): boolean {
  return getHostCapabilities().externalAgents;
}
