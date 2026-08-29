/**
 * 选品双端门禁 — 检测闲鱼 / 1688 是否具备可用登录态。
 */

import { useCallback, useEffect, useState } from "react";
import { OWNER_ID } from "@desk/platform/constants";
import {
  accountConnectionState,
  accountList,
  type XianyuAccount,
} from "@desk/platform/ipc/account";
import { listenChannelStatus } from "@desk/platform/events";
import { normalizeChannelConnectionState } from "@desk/platform";
import { resolveAccountPlatform } from "./accounts-panel";
import { ACCOUNTS_SESSION_PROBED_EVENT } from "./account-session-events";
import {
  getCachedSessionProbe,
  loadConnectedAccountIds,
} from "./use-connected-accounts";

async function xianyuHasValidSession(accounts: XianyuAccount[]): Promise<boolean> {
  const xianyuAccounts = accounts.filter(
    (account) =>
      resolveAccountPlatform(account) === "xianyu" && Boolean(account.cookie?.trim()),
  );
  if (xianyuAccounts.length === 0) {
    return false;
  }

  const connectedIds = new Set(await loadConnectedAccountIds());
  for (const account of xianyuAccounts) {
    if (!connectedIds.has(account.account_id)) {
      continue;
    }
    try {
      const state = normalizeChannelConnectionState(
        await accountConnectionState(OWNER_ID, account.account_id),
      );
      if (state === "connected") {
        return true;
      }
    } catch {
      // 单账号状态查询失败则退回探针。
    }
  }

  return platformProbeOk(xianyuAccounts);
}

async function ali1688HasValidSession(accounts: XianyuAccount[]): Promise<boolean> {
  const aliAccounts = accounts.filter(
    (account) =>
      resolveAccountPlatform(account) === "ali1688" && Boolean(account.cookie?.trim()),
  );
  return platformProbeOk(aliAccounts);
}

async function platformProbeOk(accounts: XianyuAccount[]): Promise<boolean> {
  if (accounts.length === 0) {
    return false;
  }
  return accounts.some((account) => getCachedSessionProbe(account.account_id) === true);
}

/** 选品页双端门禁：闲鱼渠道已连或登录有效，且 1688 登录有效。 */
export function useAccountGateStatus() {
  const [xianyuConnected, setXianyuConnected] = useState(false);
  const [ali1688Connected, setAli1688Connected] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const accounts = await accountList(OWNER_ID);
      const [xianyu, ali1688] = await Promise.all([
        xianyuHasValidSession(accounts),
        ali1688HasValidSession(accounts),
      ]);
      setXianyuConnected(xianyu);
      setAli1688Connected(ali1688);
    } catch {
      setXianyuConnected(false);
      setAli1688Connected(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onProbed = () => {
      void refresh();
    };
    window.addEventListener(ACCOUNTS_SESSION_PROBED_EVENT, onProbed);
    return () => {
      window.removeEventListener(ACCOUNTS_SESSION_PROBED_EVENT, onProbed);
    };
  }, [refresh]);

  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | undefined;

    void listenChannelStatus((payload) => {
      if (cancelled || !payload.account_id) {
        return;
      }
      if (
        payload.state === "connected" ||
        payload.state === "disconnected" ||
        payload.state === "auth_expired"
      ) {
        void refresh();
      }
    })
      .then((fn) => {
        if (!cancelled) {
          unlisten = fn;
        }
      })
      .catch(() => {
        // 订阅失败时仍依赖进页刷新。
      });

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [refresh]);

  return {
    xianyuConnected,
    ali1688Connected,
    canCrawl: xianyuConnected && ali1688Connected,
    loading,
    refresh,
  };
}
