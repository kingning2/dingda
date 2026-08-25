/**
 * 已连接账号持久化 + 启动登录态探针。
 *
 * 「连接」状态写入业务库；启动时对已连接账号调用 `account_probe_login`。
 *
 * @author Xiaoman
 * @created 2026-08-22
 */

import { OWNER_ID } from "@desk/platform/constants";
import { accountProbeLogin } from "@desk/platform/ipc/account";
import { userSettingGet, userSettingSet } from "@desk/platform/ipc/setting";
import type { XianyuAccount } from "@desk/platform/ipc/account";
import { enqueueWrite, parseAccountIds } from "./helpers";

const SETTING_CONNECTED_IDS = "account.connected.account_ids";

const probeCache = new Map<string, boolean>();

/** 读取曾标记为「已连接」的账号 id 列表。 */
export async function loadConnectedAccountIds(): Promise<string[]> {
  const raw = await userSettingGet(SETTING_CONNECTED_IDS);
  return [...new Set(parseAccountIds(raw))];
}

async function persistConnectedAccountIds(accountIds: string[]): Promise<void> {
  await userSettingSet(SETTING_CONNECTED_IDS, JSON.stringify([...new Set(accountIds)]));
}

/** 标记账号是否处于「已连接」配置（断开时移除）。 */
export async function setAccountConnected(accountId: string, connected: boolean): Promise<string[]> {
  return enqueueWrite(async () => {
    const current = await loadConnectedAccountIds();
    const next = new Set(current);
    if (connected) {
      next.add(accountId);
    } else {
      next.delete(accountId);
      probeCache.delete(accountId);
    }
    const accountIds = [...next];
    await persistConnectedAccountIds(accountIds);
    return accountIds;
  });
}

/** 最近一次探针结果（供面板初始化读取）。 */
export function getCachedSessionProbe(accountId: string): boolean | undefined {
  return probeCache.get(accountId);
}

/**
 * 对含 Cookie 的账号批量执行登录探针（1688 登录态面板用）。
 *
 * @returns account_id → 是否仍在线
 */
export async function probeAccountLoginSessions(
  accounts: XianyuAccount[],
): Promise<Record<string, boolean>> {
  const targets = accounts.filter((account) => Boolean(account.cookie?.trim()));
  if (targets.length === 0) {
    return {};
  }

  const results: Record<string, boolean> = {};
  await Promise.all(
    targets.map(async (account) => {
      try {
        results[account.account_id] = await accountProbeLogin(OWNER_ID, account.account_id);
      } catch {
        results[account.account_id] = false;
      }
      probeCache.set(account.account_id, results[account.account_id]);
    }),
  );
  return results;
}

/**
 * 对已连接且含 Cookie 的账号执行登录探针。
 *
 * @returns account_id → 是否仍 online
 */
export async function probeConnectedAccounts(accounts: XianyuAccount[]): Promise<Record<string, boolean>> {
  const connectedIds = new Set(await loadConnectedAccountIds());
  const targets = accounts.filter(
    (account) => connectedIds.has(account.account_id) && Boolean(account.cookie?.trim()),
  );
  if (targets.length === 0) {
    return {};
  }

  const results: Record<string, boolean> = {};
  await Promise.all(
    targets.map(async (account) => {
      try {
        results[account.account_id] = await accountProbeLogin(OWNER_ID, account.account_id);
      } catch {
        results[account.account_id] = false;
      }
      probeCache.set(account.account_id, results[account.account_id]);
    }),
  );
  return results;
}
