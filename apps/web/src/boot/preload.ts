/**
 * 应用启动预载：Server 就绪后拉齐首页所需数据，完成前不卸启动屏。
 *
 * 包含：Agent 目录（及模型缓存）、账号、最近会话。
 * 不含：OCR 预热、首次全量 Agent 深度扫描（放后台）。
 *
 * 这段编排只能待在应用装配层：它要把 Agent 域（@v2/ui-agent）与账号域
 * （@v2/ui-account）各自的发现逻辑组合起来，而两个域互不引用。早先它挂在
 * @v2/runtime 里，等于让基座包反向依赖业务包 —— 拆包后才暴露出来。
 */

import { useDiscoveryStore } from "@v2/app-state";
import { getApiBaseUrl } from "@v2/runtime/http-client";
import { kickServerWarmup } from "@v2/runtime/server";
import { refreshAccountsForPlatforms } from "@v2/ui-account/account-discovery";
import {
  loadCachedAgentRuntimes,
  refreshRecentWorks,
  rescanAgentRuntimes,
} from "@v2/ui-agent/agent-runtime-scan";

let preloadPromise: Promise<void> | null = null;
let initialLoadStarted = false;

/** Server ready 后预热首页数据；幂等。 */
export async function preloadAppHome(): Promise<void> {
  if (preloadPromise) return preloadPromise;

  preloadPromise = (async () => {
    await kickServerWarmup();
    await Promise.all([
      loadCachedAgentRuntimes({ autoScanIfEmpty: false }),
      refreshAccountsForPlatforms(),
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

/**
 * 应用启动后执行一次：Agent 缓存 + 账号 + 最近会话。
 * 若启动预载已写过 store，则直接跳过。
 */
export async function ensureDiscoveryScanned(): Promise<void> {
  if (initialLoadStarted) return;
  if (useDiscoveryStore.getState().recentWorksLoaded) {
    initialLoadStarted = true;
    return;
  }
  initialLoadStarted = true;

  await Promise.all([
    loadCachedAgentRuntimes({ autoScanIfEmpty: false }),
    refreshAccountsForPlatforms(),
    refreshRecentWorks(),
  ]);
}
