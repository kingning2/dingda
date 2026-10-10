/**
 * 最近工作会话预热。
 *
 * 职责：
 *   拉取最近工作写入 discovery store（首页 / 预加载共用）。
 */

import { useDiscoveryStore } from "@v2/app-state";
import { fetchAgentWorkList } from "./api";

/** 拉取最近工作会话写入 store（首页预热）。 */
export async function refreshRecentWorks(options?: { limit?: number }): Promise<void> {
  const { setRecentWorks, setRecentWorksLoading } = useDiscoveryStore.getState();
  setRecentWorksLoading(true);
  try {
    const items = await fetchAgentWorkList({ limit: options?.limit ?? 40 });
    setRecentWorks(items);
  } catch {
    setRecentWorks([]);
  }
}
