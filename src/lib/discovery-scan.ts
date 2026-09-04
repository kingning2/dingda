/**
 * 发现层：账号启动刷新；Agent 读 SQLite 缓存。
 * 仅「首次安装、库中无扫描结果」时自动扫一次，之后靠手动「扫描 Agent」。
 */

import type { AccountListItem, AccountPlatform } from "@/contracts/account";
import type { AgentRuntimeItem } from "@/contracts/agent-runtime";
import {
  applyAgentPreferences,
  listAgentRegistryPlaceholders,
  listAgentRuntimes,
  normalizeAgentRuntimeItem,
  probeAgentsInBackground,
} from "@/lib/agent-runtime";
import {
  fetchAgentPreferences,
  fetchAgentRuntimesCatalog,
  putAgentRuntimesCatalog,
} from "@/lib/agent-api";
import { listStoredAccounts } from "@/lib/account-store";
import { getApiBaseUrl } from "@/lib/http-client";
import { supportsExternalAgents } from "@/lib/capabilities";
import { fetchServerStatus } from "@/lib/server";
import {
  ACCOUNT_PLATFORMS,
  useDiscoveryStore,
} from "@/stores/discovery-store";

let initialLoadStarted = false;
/** 防止启动路径并发触发多次首次自动扫描。 */
let firstAutoScanStarted = false;
let cancelBackgroundProbe: (() => void) | null = null;

function commitAgents(next: AgentRuntimeItem[]) {
  useDiscoveryStore.getState().setAgents(next);
}

function normalizeCatalog(agents: AgentRuntimeItem[]): AgentRuntimeItem[] {
  return agents.map((agent) =>
    normalizeAgentRuntimeItem(agent as Parameters<typeof normalizeAgentRuntimeItem>[0]),
  );
}

async function persistAgentsCatalog(agents: AgentRuntimeItem[]): Promise<void> {
  if (!getApiBaseUrl()) return;
  try {
    await putAgentRuntimesCatalog(agents);
  } catch {
    // 落库失败不打断 UI
  }
}

/**
 * 从 SQLite 加载上次扫描目录。
 * 无缓存时先展示「未安装」占位；若 autoScanIfEmpty 则触发一次完整扫描。
 */
export async function loadCachedAgentRuntimes(options?: {
  autoScanIfEmpty?: boolean;
}): Promise<void> {
  if (!supportsExternalAgents()) {
    commitAgents([]);
    return;
  }

  let agents: AgentRuntimeItem[] = [];
  let hasCache = false;
  if (getApiBaseUrl()) {
    try {
      const [cached, preferences] = await Promise.all([
        fetchAgentRuntimesCatalog(),
        fetchAgentPreferences().catch(() => null),
      ]);
      agents = normalizeCatalog(cached);
      hasCache = agents.length > 0;
      if (preferences && hasCache) {
        agents = applyAgentPreferences(agents, preferences);
      }
    } catch {
      agents = [];
      hasCache = false;
    }
  }

  if (!hasCache) {
    agents = await listAgentRegistryPlaceholders();
    commitAgents(agents);

    const canAutoScan =
      Boolean(options?.autoScanIfEmpty) && Boolean(getApiBaseUrl()) && !firstAutoScanStarted;
    if (canAutoScan) {
      firstAutoScanStarted = true;
      await rescanAgentRuntimes(getApiBaseUrl());
    }
    return;
  }

  commitAgents(agents);
}

/** 拉取全部平台账号，合并写入 store。 */
export async function refreshDiscoveryAccounts(): Promise<void> {
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

/**
 * 应用启动后执行一次：先读 Agent 缓存 / 占位 + 刷账号。
 * 首次自动扫描等 Server 就绪后再做（见 refreshDiscoveryOnServerReady）。
 */
export async function ensureDiscoveryScanned(): Promise<void> {
  if (initialLoadStarted) return;
  initialLoadStarted = true;

  await Promise.all([
    loadCachedAgentRuntimes({ autoScanIfEmpty: Boolean(getApiBaseUrl()) }),
    refreshDiscoveryAccounts(),
  ]);
}

/** Server 就绪后：有缓存只读库；无缓存则首次自动扫描。 */
export async function refreshDiscoveryOnServerReady(): Promise<void> {
  await Promise.all([
    loadCachedAgentRuntimes({ autoScanIfEmpty: true }),
    refreshDiscoveryAccounts(),
  ]);
}

/** Server 就绪后补读 SQLite 偏好（盖到当前列表）。 */
export async function refreshDefaultAgentPreference(): Promise<void> {
  if (!supportsExternalAgents()) return;
  const current = useDiscoveryStore.getState().agents;
  if (current.length === 0) return;

  try {
    const preferences = await fetchAgentPreferences();
    commitAgents(applyAgentPreferences(current, preferences));
  } catch {
    // 偏好读取失败不打断列表
  }
}

/**
 * 用户手动「扫描 Agent」：PATH 列表 + 深度 probe，全部完成后落库。
 */
export async function rescanAgentRuntimes(
  apiBaseUrl?: string | null,
): Promise<AgentRuntimeItem[]> {
  if (!supportsExternalAgents()) {
    commitAgents([]);
    return [];
  }

  const { setAgentsScanning } = useDiscoveryStore.getState();
  setAgentsScanning(true);
  cancelBackgroundProbe?.();

  try {
    const status = apiBaseUrl ? { apiBaseUrl } : await fetchServerStatus();
    const detected = await listAgentRuntimes(status.apiBaseUrl);
    commitAgents(detected);

    const probed = await new Promise<AgentRuntimeItem[]>((resolve) => {
      cancelBackgroundProbe = probeAgentsInBackground(
        detected,
        commitAgents,
        (finalAgents) => resolve(finalAgents),
      );
    });

    let next = probed;
    try {
      const preferences = await fetchAgentPreferences({
        baseUrl: status.apiBaseUrl,
      });
      next = applyAgentPreferences(probed, preferences);
    } catch {
      // 偏好可选
    }
    commitAgents(next);
    await persistAgentsCatalog(next);
    return next;
  } finally {
    setAgentsScanning(false);
  }
}

export function probeSingleAgent(agentId: string) {
  cancelBackgroundProbe?.();
  cancelBackgroundProbe = probeAgentsInBackground(
    markSingleProbing(useDiscoveryStore.getState().agents, agentId),
    commitAgents,
    (finalAgents) => {
      void persistAgentsCatalog(finalAgents);
    },
  );
}

function markSingleProbing(
  agents: AgentRuntimeItem[],
  agentId: string,
): AgentRuntimeItem[] {
  return agents.map((agent) =>
    agent.id === agentId
      ? {
          ...agent,
          status: {
            state: "probing",
            label: "检测中…",
            hint: null,
            badge_class: "bg-sky-500/15 text-sky-700",
          },
        }
      : agent,
  );
}

/** 刷新单个平台账号后合并进 store。 */
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
