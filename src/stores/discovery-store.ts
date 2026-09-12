/**
 * 启动探测结果（Agent CLI + 平台账号 + 最近会话）的全局状态。
 * 预热写这里，首页 / 项目页只订阅下发。
 */

import { create } from "zustand";

import type { AccountListItem, AccountPlatform } from "@v2/contracts/account";
import type { AgentRuntimeItem } from "@v2/contracts/agent-runtime";
import type { AgentWorkSummary } from "@/lib/agent-api";
import { supportsExternalAgents } from "@/lib/capabilities";

export const ACCOUNT_PLATFORMS: AccountPlatform[] = [
  "xianyu",
  "ali1688",
  "xiaohongshu",
];

type DiscoveryState = {
  agents: AgentRuntimeItem[];
  agentsScanning: boolean;

  accounts: AccountListItem[];
  autoConnectIds: string[];
  accountsLoading: boolean;
  accountsError: string | null;
  accountsLoaded: boolean;

  /** 最近工作会话（首页 / 全部项目共用）。 */
  recentWorks: AgentWorkSummary[];
  recentWorksLoading: boolean;
  recentWorksLoaded: boolean;

  setAgents: (agents: AgentRuntimeItem[]) => void;
  setAgentsScanning: (scanning: boolean) => void;

  setAccountsSnapshot: (
    accounts: AccountListItem[],
    autoConnectIds: string[],
  ) => void;
  upsertAccount: (account: AccountListItem) => void;
  removeAccount: (accountId: string) => void;
  setAutoConnectIds: (ids: string[]) => void;
  setAccountsLoading: (loading: boolean) => void;
  setAccountsError: (error: string | null) => void;

  setRecentWorks: (works: AgentWorkSummary[]) => void;
  setRecentWorksLoading: (loading: boolean) => void;
};

export const useDiscoveryStore = create<DiscoveryState>((set) => ({
  agents: supportsExternalAgents() ? [] : [],
  agentsScanning: false,

  accounts: [],
  autoConnectIds: [],
  accountsLoading: false,
  accountsError: null,
  accountsLoaded: false,

  recentWorks: [],
  recentWorksLoading: false,
  recentWorksLoaded: false,

  setAgents: (agents) =>
    set((state) => (state.agents === agents ? state : { agents })),
  setAgentsScanning: (agentsScanning) =>
    set((state) => (state.agentsScanning === agentsScanning ? state : { agentsScanning })),

  setAccountsSnapshot: (accounts, autoConnectIds) =>
    set({
      accounts,
      autoConnectIds,
      accountsLoaded: true,
      accountsError: null,
    }),

  upsertAccount: (account) =>
    set((state) => {
      const exists = state.accounts.some(
        (item) => item.account_id === account.account_id,
      );
      return {
        accounts: exists
          ? state.accounts.map((item) =>
              item.account_id === account.account_id ? account : item,
            )
          : [account, ...state.accounts],
      };
    }),

  removeAccount: (accountId) =>
    set((state) => ({
      accounts: state.accounts.filter((item) => item.account_id !== accountId),
      autoConnectIds: state.autoConnectIds.filter((id) => id !== accountId),
    })),

  setAutoConnectIds: (autoConnectIds) => set({ autoConnectIds }),
  setAccountsLoading: (accountsLoading) => set({ accountsLoading }),
  setAccountsError: (accountsError) => set({ accountsError }),

  setRecentWorks: (recentWorks) =>
    set({
      recentWorks,
      recentWorksLoaded: true,
      recentWorksLoading: false,
    }),
  setRecentWorksLoading: (recentWorksLoading) => set({ recentWorksLoading }),
}));

export function getDiscoveryAgents(): AgentRuntimeItem[] {
  return useDiscoveryStore.getState().agents;
}

export function getDiscoveryAccounts(platform?: AccountPlatform): AccountListItem[] {
  const accounts = useDiscoveryStore.getState().accounts;
  if (!platform) return accounts;
  return accounts.filter((item) => item.platform === platform);
}
