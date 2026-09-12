/**
 * 应用预加载：Server 就绪后拉齐首页所需数据，完成前不卸启动屏。
 *
 * 包含：Agent 目录（及模型缓存）、账号、最近会话。
 * 不含：OCR 预热、首次全量 Agent 深度扫描（放后台）。
 */

import { dismissBootSplash } from "./dismiss-boot-splash";
import {
  loadCachedAgentRuntimes,
  refreshDiscoveryAccounts,
  refreshRecentWorks,
  rescanAgentRuntimes,
} from "@v2/ui-crawler/discovery-scan";
import { getApiBaseUrl } from "./http-client";
import { kickServerWarmup } from "./server";
import { useDiscoveryStore } from "@v2/ui-crawler/discovery-store";

let preloadPromise: Promise<void> | null = null;

/** Server ready 后预热首页数据；幂等。 */
export async function preloadAppHome(): Promise<void> {
  if (preloadPromise) return preloadPromise;

  preloadPromise = (async () => {
    await kickServerWarmup();
    await Promise.all([
      loadCachedAgentRuntimes({ autoScanIfEmpty: false }),
      refreshDiscoveryAccounts(),
      refreshRecentWorks({ limit: 40 }),
    ]);

    // 无已安装 Agent 时后台扫描，不挡进首页
    const agents = useDiscoveryStore.getState().agents;
    const hasInstalled = agents.some((agent) => agent.available);
    if (!hasInstalled && getApiBaseUrl()) {
      void rescanAgentRuntimes(getApiBaseUrl());
    }
  })();

  try {
    await preloadPromise;
  } catch (error) {
    console.warn("app preload failed", error);
    preloadPromise = null;
    throw error;
  }
}

/** 预加载结束后淡出启动屏。 */
export function finishBootSplash(): void {
  dismissBootSplash();
}
