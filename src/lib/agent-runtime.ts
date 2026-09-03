import { invoke, isTauri } from "@tauri-apps/api/core";

import type {
  AgentListResponse,
  AgentRuntimeAuthView,
  AgentRuntimeItem,
  AgentRuntimeLoginResult,
  AgentRuntimeProbeResult,
  AgentRuntimeStatusView,
} from "@/contracts/agent-runtime";

let mockCodexAuthenticated = false;

type RawAgentRuntimeItem = AgentRuntimeItem & {
  installUrl?: string | null;
  docsUrl?: string | null;
  isDefault?: boolean;
  externalMcpInjection?: string | null;
  canLogin?: boolean;
  canProbe?: boolean;
  source?: string | null;
  status?: RawAgentRuntimeStatusView;
};

type RawAgentRuntimeStatusView = AgentRuntimeStatusView & {
  badgeClass?: string;
};

export function getAgentGuideUrl(agent: AgentRuntimeItem): string | null {
  const docs = agent.docs_url?.trim();
  const install = agent.install_url?.trim();
  return docs || install || null;
}

export function supportsAgentLogin(agent: AgentRuntimeItem): boolean {
  return Boolean(agent.can_login);
}

export function supportsAgentProbe(_agent: AgentRuntimeItem): boolean {
  return true;
}

export function normalizeAgentRuntimeItem(raw: RawAgentRuntimeItem): AgentRuntimeItem {
  const status = raw.status;
  return {
    id: raw.id,
    name: raw.name,
    description: raw.description,
    available: raw.available,
    version: raw.version ?? null,
    command: raw.command ?? null,
    source: raw.source ?? null,
    install_url: raw.install_url ?? raw.installUrl ?? null,
    docs_url: raw.docs_url ?? raw.docsUrl ?? null,
    is_default: raw.is_default ?? raw.isDefault ?? false,
    external_mcp_injection: raw.external_mcp_injection ?? raw.externalMcpInjection ?? null,
    auth: raw.auth ?? null,
    models: raw.models ?? null,
    can_login: raw.can_login ?? raw.canLogin,
    can_probe: raw.can_probe ?? raw.canProbe,
    status: {
      state: status?.state ?? "missing",
      label: status?.label ?? "未知",
      hint: status?.hint ?? null,
      badge_class: status?.badge_class ?? status?.badgeClass ?? "bg-muted text-muted-foreground",
    },
  };
}

export async function listAgentRuntimes(): Promise<AgentRuntimeItem[]> {
  if (isTauri()) {
    const response = await invoke<AgentListResponse>("list_agent_runtimes_command");
    return response.agents.map((agent) => normalizeAgentRuntimeItem(agent as RawAgentRuntimeItem));
  }
  return [];
}

export function buildAuthView(
  agentId: string,
  authenticated: boolean | null,
): AgentRuntimeAuthView | null {
  if (agentId !== "codex") return null;
  if (authenticated === null) {
    return {
      state: "unknown",
      label: "未检测",
      can_login: true,
      hint: "点击「扫描 Agent」查看登录状态",
    };
  }
  if (authenticated) {
    return {
      state: "authenticated",
      label: "已登录",
      can_login: false,
    };
  }
  return {
    state: "unauthenticated",
    label: "未登录",
    can_login: true,
    hint: "点击「登录」将调用 codex login 打开浏览器完成授权",
  };
}

function mergeProbeResult(agent: AgentRuntimeItem, raw: AgentRuntimeProbeResult): AgentRuntimeItem {
  if (!raw.available) {
    return {
      ...agent,
      available: false,
      command: raw.command ?? agent.command ?? null,
      source: raw.source ?? agent.source ?? null,
      version: raw.version ?? null,
      auth: supportsAgentLogin(agent) ? buildAuthView(agent.id, null) : null,
      models: null,
      status: {
        state: "missing",
        label: "未安装",
        hint: raw.error ?? null,
        badge_class: "bg-muted text-muted-foreground",
      },
    };
  }

  const authenticated = raw.authenticated ?? null;
  const auth = buildAuthView(agent.id, authenticated);
  const models = raw.models?.length ? raw.models : null;

  return {
    ...agent,
    available: true,
    command: raw.command ?? agent.command ?? null,
    version: raw.version ?? agent.version ?? null,
    auth,
    models,
    status: authenticated
      ? {
          state: "ready",
          label: "已就绪",
          hint: null,
          badge_class: "bg-emerald-500/15 text-emerald-600",
        }
      : supportsAgentLogin(agent)
        ? {
            state: "auth_required",
            label: "待登录",
            hint: "请先登录 Codex CLI",
            badge_class: "bg-amber-500/15 text-amber-700",
          }
        : {
            state: "ready",
            label: "已就绪",
            hint: null,
            badge_class: "bg-emerald-500/15 text-emerald-600",
          },
  };
}

export async function probeAgentRuntime(agent: AgentRuntimeItem): Promise<AgentRuntimeItem> {
  if (isTauri() && supportsAgentProbe(agent)) {
    try {
      const raw = await invoke<AgentRuntimeProbeResult>("probe_agent_runtime", {
        agentId: agent.id,
      });
      return mergeProbeResult(agent, raw);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return mergeProbeResult(agent, {
        available: false,
        error: message,
      });
    }
  }

  await delay(500);
  if (!agent.available) return agent;

  if (agent.id === "codex") {
    const authenticated = mockCodexAuthenticated;
    return mergeProbeResult(agent, {
      available: true,
      authenticated,
      models: authenticated
        ? [
            { id: "gpt-5.5", label: "GPT-5.5" },
            { id: "gpt-5.4", label: "GPT-5.4" },
          ]
        : [{ id: "gpt-5.5", label: "GPT-5.5" }],
      command: agent.command,
      version: agent.version,
    });
  }

  if (agent.id === "claude") {
    return mergeProbeResult(agent, {
      available: true,
      models: [
        { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
        { id: "claude-opus-4-6", label: "Claude Opus 4.6" },
      ],
      command: agent.command,
      version: agent.version,
    });
  }

  return {
    ...agent,
    status: {
      state: "ready",
      label: "已就绪",
      hint: null,
      badge_class: "bg-emerald-500/15 text-emerald-600",
    },
  };
}

const PROBING_STATUS: AgentRuntimeStatusView = {
  state: "probing",
  label: "检测中…",
  hint: null,
  badge_class: "bg-sky-500/15 text-sky-700",
};

function markAgentProbing(agent: AgentRuntimeItem): AgentRuntimeItem {
  return { ...agent, status: PROBING_STATUS };
}

function markAgentsProbing(agents: AgentRuntimeItem[], agentIds: Set<string>): AgentRuntimeItem[] {
  return agents.map((agent) => (agentIds.has(agent.id) ? markAgentProbing(agent) : agent));
}

function replaceAgent(agents: AgentRuntimeItem[], updated: AgentRuntimeItem): AgentRuntimeItem[] {
  return agents.map((agent) => (agent.id === updated.id ? updated : agent));
}

/** 将后端 PATH 探测结果合并进列表，不触发慢速 probe（模型/版本留待后台更新）。 */
export function mergeListDetection(
  base: AgentRuntimeItem[],
  detected: AgentRuntimeItem[],
): AgentRuntimeItem[] {
  const detectedById = new Map(detected.map((agent) => [agent.id, agent]));
  return base.map((agent) => {
    const fresh = detectedById.get(agent.id);
    if (!fresh) return agent;
    return {
      ...agent,
      available: fresh.available,
      install_url: fresh.install_url ?? agent.install_url,
      docs_url: fresh.docs_url ?? agent.docs_url,
      is_default: fresh.is_default ?? agent.is_default,
      external_mcp_injection: fresh.external_mcp_injection ?? agent.external_mcp_injection,
      can_login: fresh.can_login ?? agent.can_login,
      can_probe: fresh.can_probe ?? agent.can_probe,
      command: fresh.available ? (fresh.command ?? agent.command ?? null) : null,
      source: fresh.available ? (fresh.source ?? agent.source ?? null) : null,
      version: null,
      auth: fresh.available && supportsAgentLogin(agent) ? buildAuthView(agent.id, null) : null,
      models: null,
      status: fresh.available
        ? PROBING_STATUS
        : {
            state: "missing",
            label: "未安装",
            hint: fresh.status.hint ?? null,
            badge_class: "bg-muted text-muted-foreground",
          },
    };
  });
}

/**
 * 后台并行 probe 已安装的 Agent，按帧合并 onUpdate（避免每个 Agent 完成都触发订阅）。
 * 返回取消函数。
 */
export function probeAgentsInBackground(
  agents: AgentRuntimeItem[],
  onUpdate: (agents: AgentRuntimeItem[]) => void,
): () => void {
  let cancelled = false;
  const targets = agents.filter((agent) => agent.available);
  if (targets.length === 0) return () => undefined;

  const probingIds = new Set(targets.map((agent) => agent.id));
  let snapshot = markAgentsProbing(agents, probingIds);
  onUpdate(snapshot);

  let rafId: number | null = null;

  const flush = () => {
    rafId = null;
    if (cancelled) return;
    onUpdate([...snapshot]);
  };

  const scheduleFlush = () => {
    if (rafId !== null) return;
    rafId = requestAnimationFrame(flush);
  };

  void (async () => {
    await Promise.all(
      targets.map(async (agent) => {
        const probed = await probeAgentRuntime(agent);
        if (cancelled) return;
        snapshot = replaceAgent(snapshot, probed);
        scheduleFlush();
      }),
    );
    if (cancelled) return;
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    flush();
  })();

  return () => {
    cancelled = true;
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  };
}

export async function enrichAvailableAgents(agents: AgentRuntimeItem[]): Promise<AgentRuntimeItem[]> {
  const available = agents.filter((agent) => agent.available);
  if (available.length === 0) return agents;

  const probed = await Promise.all(available.map((agent) => probeAgentRuntime(agent)));
  const probedById = new Map(probed.map((agent) => [agent.id, agent]));
  return agents.map((agent) => probedById.get(agent.id) ?? agent);
}

export async function loginAgentRuntime(agentId: string): Promise<AgentRuntimeLoginResult> {
  if (isTauri()) {
    try {
      return await invoke<AgentRuntimeLoginResult>("login_agent_runtime", { agentId });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { started: false, message };
    }
  }

  await delay(400);
  if (agentId !== "codex") {
    return { started: false, message: "该 Agent 暂不支持从平台登录" };
  }

  mockCodexAuthenticated = true;
  return {
    started: true,
    message: "已调用 codex login（mock）。实际环境会在浏览器中完成授权，完成后请点击「扫描 Agent」。",
  };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
