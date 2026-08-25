/**
 * 启动自动连接：配置写入业务库；只连勾选的闲鱼账号；1688 可勾选但不走渠道连接。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */

import { OWNER_ID } from "@desk/platform/constants";
import { useEffect, useRef } from "react";
import {
  accountConnect,
  accountList,
  type XianyuAccount,
} from "@desk/platform/ipc/account";
import { listenChannelStatus } from "@desk/platform/events";
import { logWrite } from "@desk/platform/ipc/log";
import { userSettingGet, userSettingSet } from "@desk/platform/ipc/setting";
import { resolveAccountPlatform } from "./accounts-panel";
import { loadConnectedAccountIds, probeConnectedAccounts } from "./use-connected-accounts";
import { enqueueWrite, parseAccountIds } from "./helpers";

const SETTING_ENABLED = "account.auto_connect.enabled";
const SETTING_ACCOUNT_IDS = "account.auto_connect.account_ids";
const LEGACY_XIANYU_ENABLED = "xianyu.auto_connect.enabled";
const LEGACY_XIANYU_IDS = "xianyu.auto_connect.account_ids";
const LEGACY_ENABLED_KEY = "dingda.xianyu.auto_connect_on_start";
const LEGACY_SELECTED_KEY = "dingda.xianyu.auto_connect_account_ids";

/** 风控未解决时的重连间隔（毫秒）。 */
export const AUTO_CONNECT_RETRY_MS = 10 * 60 * 1000;
const STAGGER_MS = 2500;

interface AutoConnectConfig {
  enabled: boolean;
  accountIds: string[];
}

let cached: AutoConnectConfig = { enabled: false, accountIds: [] };

function readLegacyFromLocalStorage(): AutoConnectConfig | null {
  if (typeof window === "undefined") {
    return null;
  }
  const enabledRaw = window.localStorage.getItem(LEGACY_ENABLED_KEY);
  const idsRaw = window.localStorage.getItem(LEGACY_SELECTED_KEY);
  if (enabledRaw === null && idsRaw === null) {
    return null;
  }
  return {
    enabled: enabledRaw === "true",
    accountIds: parseAccountIds(idsRaw),
  };
}

function clearLegacyLocalStorage(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(LEGACY_ENABLED_KEY);
  window.localStorage.removeItem(LEGACY_SELECTED_KEY);
}

/**
 * 从业务库读取自动连接配置（并刷新内存缓存）。
 *
 * 兼容旧版 `xianyu.auto_connect.*` 与 localStorage 键名。
 *
 * @returns 总开关与勾选账号 id
 */
export async function loadAutoConnectConfig(): Promise<AutoConnectConfig> {
  const [enabledRaw, idsRaw, legacyEnabledRaw, legacyIdsRaw] = await Promise.all([
    userSettingGet(SETTING_ENABLED),
    userSettingGet(SETTING_ACCOUNT_IDS),
    userSettingGet(LEGACY_XIANYU_ENABLED),
    userSettingGet(LEGACY_XIANYU_IDS),
  ]);

  if (enabledRaw === null && idsRaw === null) {
    if (legacyEnabledRaw !== null || legacyIdsRaw !== null) {
      const migrated = {
        enabled: legacyEnabledRaw === "true",
        accountIds: parseAccountIds(legacyIdsRaw),
      };
      await persistAutoConnectConfig(migrated);
      cached = migrated;
      return migrated;
    }
    const legacy = readLegacyFromLocalStorage();
    if (legacy) {
      await persistAutoConnectConfig(legacy);
      clearLegacyLocalStorage();
      cached = legacy;
      return legacy;
    }
  }

  cached = {
    enabled: enabledRaw === "true",
    accountIds: parseAccountIds(idsRaw),
  };
  return cached;
}

async function persistAutoConnectConfig(config: AutoConnectConfig): Promise<void> {
  cached = {
    enabled: config.enabled,
    accountIds: [...new Set(config.accountIds)],
  };
  await Promise.all([
    userSettingSet(SETTING_ENABLED, cached.enabled ? "true" : "false"),
    userSettingSet(SETTING_ACCOUNT_IDS, JSON.stringify(cached.accountIds)),
  ]);
}

/**
 * 写入总开关到业务库。
 *
 * @param enabled - 是否开启
 */
export async function setAutoConnectOnStartEnabled(enabled: boolean): Promise<void> {
  await enqueueWrite(async () => {
    const current = await loadAutoConnectConfig();
    await persistAutoConnectConfig({ ...current, enabled });
  });
}

/**
 * 切换单个账号是否参与自动连接（写入业务库）。
 *
 * @param accountId - 账号 id
 * @param selected - 是否勾选
 * @returns 更新后的勾选列表
 */
export async function setAccountAutoConnect(
  accountId: string,
  selected: boolean,
): Promise<string[]> {
  return enqueueWrite(async () => {
    const current = await loadAutoConnectConfig();
    const next = new Set(current.accountIds);
    if (selected) {
      next.add(accountId);
    } else {
      next.delete(accountId);
    }
    const accountIds = [...next];
    await persistAutoConnectConfig({ ...current, accountIds });
    return accountIds;
  });
}

function isSelectedActiveWithCookie(account: XianyuAccount, selectedIds: Set<string>): boolean {
  return (
    selectedIds.has(account.account_id) &&
    account.status === "active" &&
    Boolean(account.cookie?.trim())
  );
}

/** 启动时需发起闲鱼渠道连接的账号。 */
function isSelectedXianyuConnectable(account: XianyuAccount, selectedIds: Set<string>): boolean {
  return isSelectedActiveWithCookie(account, selectedIds) && resolveAccountPlatform(account) === "xianyu";
}

function isChannelAutoConnectTarget(accountId: string): boolean {
  return !accountId.startsWith("1688:");
}

/**
 * 连接勾选的闲鱼账号（错开启动）；1688 勾选仅保留在配置中。
 *
 * @param accounts - 账号列表
 * @param reason - 日志原因
 * @returns 实际发起连接的数量
 */
async function connectSelectedAccounts(
  accounts: XianyuAccount[],
  reason: string,
): Promise<number> {
  const config = await loadAutoConnectConfig();
  const selectedIds = new Set(config.accountIds);
  const targets = accounts.filter((account) => isSelectedXianyuConnectable(account, selectedIds));
  const selected1688 = accounts.filter(
    (account) =>
      isSelectedActiveWithCookie(account, selectedIds) &&
      resolveAccountPlatform(account) === "ali1688",
  ).length;

  if (targets.length === 0) {
    const detail =
      selected1688 > 0
        ? `；${selected1688} 个 1688 账号已勾选（无需渠道连接）`
        : "";
    void logWrite(`自动连接跳过（${reason}）：未勾选可连接的闲鱼账号${detail}`, "INFO").catch(
      () => {},
    );
    return 0;
  }

  void logWrite(
    `自动连接开始（${reason}）：${targets.length} 个闲鱼账号${
      selected1688 > 0 ? `；${selected1688} 个 1688 账号已勾选` : ""
    }`,
    "INFO",
  ).catch(() => {});

  for (let index = 0; index < targets.length; index += 1) {
    const account = targets[index];
    if (index > 0) {
      await new Promise((resolve) => {
        window.setTimeout(resolve, STAGGER_MS);
      });
    }
    try {
      const state = await accountConnect(OWNER_ID, account.account_id);
      void logWrite(
        `自动连接 ${account.account_id} → ${state}`,
        state === "connected" ? "INFO" : "WARN",
      ).catch(() => {});
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      void logWrite(`自动连接失败 ${account.account_id}: ${message}`, "WARN").catch(
        () => {},
      );
    }
  }
  return targets.length;
}

function shouldHandleAccount(accountId: string): boolean {
  return (
    cached.enabled &&
    cached.accountIds.includes(accountId) &&
    isChannelAutoConnectTarget(accountId)
  );
}

/**
 * 应用级钩子：启动只连勾选闲鱼账号 + 风控 error 十分钟重试。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */
export function useAccountAutoConnect(): void {
  const startedRef = useRef(false);
  const retryTimersRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    const retryTimers = retryTimersRef.current;

    const clearRetry = (accountId: string) => {
      const timer = retryTimersRef.current.get(accountId);
      if (timer !== undefined) {
        window.clearTimeout(timer);
        retryTimersRef.current.delete(accountId);
      }
    };

    const scheduleRetry = (accountId: string) => {
      if (!shouldHandleAccount(accountId)) {
        return;
      }
      if (retryTimersRef.current.has(accountId)) {
        return;
      }
      const timer = window.setTimeout(() => {
        retryTimersRef.current.delete(accountId);
        if (!shouldHandleAccount(accountId)) {
          return;
        }
        void logWrite(`闲鱼风控未过滑块，10 分钟后重连 ${accountId}`, "INFO").catch(() => {});
        void accountConnect(OWNER_ID, accountId)
          .then((state) => {
            void logWrite(`定时重连 ${accountId} → ${state}`, "INFO").catch(() => {});
            if (state === "error") {
              scheduleRetry(accountId);
            }
          })
          .catch((error) => {
            const message = error instanceof Error ? error.message : String(error);
            void logWrite(`定时重连失败 ${accountId}: ${message}`, "WARN").catch(() => {});
            scheduleRetry(accountId);
          });
      }, AUTO_CONNECT_RETRY_MS);
      retryTimersRef.current.set(accountId, timer);
      void logWrite(`已安排 ${accountId} 于 10 分钟后自动重连`, "INFO").catch(() => {});
    };

    let cancelled = false;
    let unlisten: (() => void) | undefined;

    void listenChannelStatus((payload) => {
      if (cancelled || !payload.account_id) {
        return;
      }
      if (payload.state === "connected" || payload.state === "disconnected") {
        clearRetry(payload.account_id);
        return;
      }
      if (payload.state === "error") {
        scheduleRetry(payload.account_id);
      }
    })
      .then((fn) => {
        if (cancelled) {
          fn();
          return;
        }
        unlisten = fn;
      })
      .catch(() => {});

    void loadAutoConnectConfig()
      .then((config) => {
        if (cancelled || startedRef.current || !config.enabled) {
          return undefined;
        }
        const forceDevAutoConnect =
          import.meta.env.VITE_FORCE_AUTO_CONNECT === "1" ||
          import.meta.env.VITE_FORCE_AUTO_CONNECT === "true";
        if (import.meta.env.DEV && !forceDevAutoConnect) {
          void logWrite(
            "开发模式跳过启动自动连接（改代码重编译会断 WS；需要时手动连接，或设 VITE_FORCE_AUTO_CONNECT=1）",
            "INFO",
          ).catch(() => {});
          return undefined;
        }
        startedRef.current = true;
        return accountList(OWNER_ID).then(async (list) => {
          if (!cancelled) {
            const connectedIds = new Set(await loadConnectedAccountIds());
            if (connectedIds.size > 0) {
              const probeResults = await probeConnectedAccounts(list);
              const expired = Object.entries(probeResults).filter(([, ok]) => !ok);
              if (expired.length > 0) {
                void logWrite(
                  `启动登录探针：${expired.length} 个已连接账号登录态已过期`,
                  "WARN",
                ).catch(() => {});
              }
            }
            return connectSelectedAccounts(list, "应用启动");
          }
          return undefined;
        });
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        void logWrite(`启动自动连接失败: ${message}`, "WARN").catch(() => {});
      });

    return () => {
      cancelled = true;
      unlisten?.();
      for (const timer of retryTimers.values()) {
        window.clearTimeout(timer);
      }
      retryTimers.clear();
    };
  }, []);
}

/** @deprecated 使用 {@link useAccountAutoConnect} */
export const useXianyuAutoConnect = useAccountAutoConnect;

/**
 * 立刻对勾选闲鱼账号执行一轮自动连接。
 *
 * @returns 实际发起连接的数量
 */
export async function runAutoConnectNow(): Promise<number> {
  const list = await accountList(OWNER_ID);
  return connectSelectedAccounts(list, "手动触发");
}
