/**
 * Agent 运行时发现：读 SQLite 缓存 → 后台补探测 → 用户手动全量扫描。
 *
 * 与账号发现（@v2/ui-account/account-discovery）刻意分开：两者写同一份 store
 * （@v2/app-state），但各自只管自己那半边，互不引用。需要「一起做」的启动编排
 * 属于应用层，放在 apps/web/src/boot 组合，不在这里。
 *
 * 本文件早先是 ui-crawler/discovery-scan 的转发壳（「兼容旧 import」）。那种壳
 * 会让依赖图看起来像 ui-agent → ui-crawler → ui-agent，把环掩盖在转发层里。
 * 实现归位后 ui-agent 不再需要认识 ui-crawler。
 */

import type { AgentRuntimeItem } from "@v2/contracts/agent-runtime";
import { useDiscoveryStore } from "@v2/app-state";
import { supportsExternalAgents } from "@v2/runtime/capabilities";
import { getApiBaseUrl } from "@v2/runtime/http-client";
import { fetchServerStatus } from "@v2/runtime/server";

import { AGENT_CATALOG } from "./agent-catalog";
import {
  applyAgentPreferences,
  listAgentRegistryPlaceholders,
  listAgentRuntimes,
  normalizeAgentRuntimeItem,
  probeAgentsInBackground,
} from "./agent-runtime";
import {
  fetchAgentPreferences,
  fetchAgentRuntimesCatalog,
  fetchAgentWorkList,
  putAgentRuntimesCatalog,
} from "./agent-api";

/** 防止启动路径并发触发多次首次自动扫描。 */
let firstAutoScanStarted = false;
let cancelBackgroundProbe: (() => void) | null = null;

const SUPPORTED_AGENT_IDS = new Set(AGENT_CATALOG.map((entry) => entry.id));

function filterSupportedAgents(agents: AgentRuntimeItem[]): AgentRuntimeItem[] {
  return agents.filter((agent) => SUPPORTED_AGENT_IDS.has(agent.id));
}

/** 旧缓存缺新注册 Agent 时，用注册表占位补齐，避免卡片消失。 */
function mergeCatalogCoverage(
  agents: AgentRuntimeItem[],
  placeholders: AgentRuntimeItem[],
): AgentRuntimeItem[] {
  const byId = new Map(filterSupportedAgents(agents).map((agent) => [agent.id, agent]));
  for (const placeholder of placeholders) {
    if (!SUPPORTED_AGENT_IDS.has(placeholder.id) || byId.has(placeholder.id)) continue;
    byId.set(placeholder.id, placeholder);
  }
  return AGENT_CATALOG.map((entry) => byId.get(entry.id)).filter(
    (agent): agent is AgentRuntimeItem => agent != null,
  );
}

function commitAgents(next: AgentRuntimeItem[]) {
  useDiscoveryStore.getState().setAgents(filterSupportedAgents(next));
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

  const placeholders = await listAgentRegistryPlaceholders();
  if (!hasCache) {
    agents = placeholders;
    commitAgents(agents);

    const canAutoScan =
      Boolean(options?.autoScanIfEmpty) && Boolean(getApiBaseUrl()) && !firstAutoScanStarted;
    if (canAutoScan) {
      firstAutoScanStarted = true;
      await rescanAgentRuntimes(getApiBaseUrl());
    }
    return;
  }

  commitAgents(mergeCatalogCoverage(agents, placeholders));

  // 缓存有目录但模型为空时，后台补探测（不挡首屏）
  const needsModels = agents.some(
    (agent) => agent.available && (!agent.models || agent.models.length === 0),
  );
  if (needsModels) {
    cancelBackgroundProbe?.();
    cancelBackgroundProbe = probeAgentsInBackground(
      useDiscoveryStore.getState().agents,
      commitAgents,
      (finalAgents) => {
        void persistAgentsCatalog(finalAgents);
      },
    );
  }
}

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
    const placeholders = await listAgentRegistryPlaceholders();
    const covered = mergeCatalogCoverage(detected, placeholders);
    commitAgents(covered);

    const probed = await new Promise<AgentRuntimeItem[]>((resolve) => {
      cancelBackgroundProbe = probeAgentsInBackground(
        covered,
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
