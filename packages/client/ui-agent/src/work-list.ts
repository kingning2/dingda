/**
 * 工作列表预热。
 *
 * 与账号发现（@v2/ui-account/account-discovery）刻意分开：两者写同一份 store
 * （@v2/app-state），但各自只管自己那半边，互不引用。需要「一起做」的启动编排
 * 属于应用层，放在 apps/web/src/boot 组合，不在这里。
 */

import { useDiscoveryStore } from "@v2/app-state";
import { getApiBaseUrl } from "@v2/runtime/http-client";

import { fetchAgentWorkList } from "./api";

/** 拉取最近工作会话写入 store（首页预热）。 */
export async function refreshRecentWorks(options?: { limit?: number }): Promise<void> {
  if (!getApiBaseUrl()) return;

  const { setRecentWorks, setRecentWorksLoading } = useDiscoveryStore.getState();
  setRecentWorksLoading(true);
  try {
    const items = await fetchAgentWorkList({ limit: options?.limit ?? 40 });
    setRecentWorks(items);
  } catch {
    setRecentWorks([]);
  }
}
