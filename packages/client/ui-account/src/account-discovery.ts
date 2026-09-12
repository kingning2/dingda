/**
 * 账号发现：启动时拉全部平台账号；扫码登录 / 解绑后只刷单个平台。
 *
 * 与 Agent 发现（@v2/ui-agent/agent-runtime-scan）刻意分开：两者写同一份 store
 * （@v2/app-state），但各自只管自己那半边，互不引用。需要「一起做」的启动编排
 * 属于应用层，放在 apps/web/src/boot 组合。
 */

import type { AccountListItem, AccountPlatform } from "@v2/contracts/account";
import { ACCOUNT_PLATFORMS, useDiscoveryStore } from "@v2/app-state";
import { getApiBaseUrl } from "@v2/runtime/http-client";

import { listStoredAccounts } from "./account-store";

/** 拉取全部平台账号，合并写入 store。 */
export async function refreshAccountsForPlatforms(): Promise<void> {
  if (!getApiBaseUrl()) return;

  const { setAccountsLoading, setAccountsError, setAccountsSnapshot } =
    useDiscoveryStore.getState();

  setAccountsLoading(true);
  try {
    const results = await Promise.all(
      ACCOUNT_PLATFORMS.map(async (platform) => {
        try {
          const data = await listStoredAccounts(platform);
          return { ...data, error: null as string | null };
        } catch (error) {
          return {
            accounts: [] as AccountListItem[],
            autoConnectIds: [] as string[],
            error: error instanceof Error ? error.message : "加载账号失败",
          };
        }
      }),
    );

    const accounts: AccountListItem[] = [];
    const autoConnectIds: string[] = [];
    let firstError: string | null = null;

    for (const result of results) {
      if (result.error && !firstError) firstError = result.error;
      accounts.push(...result.accounts);
      autoConnectIds.push(...result.autoConnectIds);
    }

    setAccountsSnapshot(accounts, autoConnectIds);
    setAccountsError(firstError);
  } catch (error) {
    setAccountsError(error instanceof Error ? error.message : "加载账号失败");
  } finally {
    setAccountsLoading(false);
  }
}

/** 刷新单个平台账号后合并进 store（不影响其它平台已加载的数据）。 */
export async function refreshAccountsForPlatform(
  platform: AccountPlatform,
): Promise<void> {
  if (!getApiBaseUrl()) return;

  const result = await listStoredAccounts(platform);
  const state = useDiscoveryStore.getState();
  const others = state.accounts.filter((item) => item.platform !== platform);
  const keptAuto = state.autoConnectIds.filter((id) =>
    others.some((account) => account.account_id === id),
  );

  state.setAccountsSnapshot(
    [...result.accounts, ...others],
    [...new Set([...result.autoConnectIds, ...keptAuto])],
  );
}
