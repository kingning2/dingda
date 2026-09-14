/**
 * 外部 CLI Runtime 的探测与操作。
 *
 * 职责：
 *   PATH 探测、鉴权视图组装、后台并发 probe、登录、下载，以及把原始字段规整成 AgentRuntimeItem。
 *
 * 设计说明：
 *   - 本文件已混装四类职责（探测 / 鉴权 / 下载 / 浏览器 mock），432 行 / 14 个顶层导出，
 *     按 frontend-coding 应拆成 cli/{probe,login,download,normalize}.ts（见 README「已知结构问题」）
 *   - mock 分支（mockCodexAuthenticated / mockClaudeAuthenticated / delay）与生产代码混装，
 *     违反 frontend-architecture 反例第 6 条「浏览器 mock 已安装 Codex/Claude」，待移除
 */

import { invoke, isTauri } from "@tauri-apps/api/core";

import type {
  AgentListResponse,
  AgentRuntimeAuthView,
  AgentRuntimeItem,
  AgentRuntimeLoginResult,
  AgentRuntimeProbeResult,
  AgentRuntimeStatusView,
} from "@v2/contracts/agent-runtime";
import { fetchAgentPreferences } from "./agent-api";

let mockCodexAuthenticated = false;
let mockClaudeAuthenticated = false;

  type RawAgentRuntimeItem = AgentRuntimeItem & {
  installUrl?: string | null;
  docsUrl?: string | null;
  isDefault?: boolean;
  externalMcpInjection?: string | null;
  canLogin?: boolean;
  canProbe?: boolean;
  canDownload?: boolean;
  source?: string | null;
  status?: RawAgentRuntimeStatusView;
};

type RawAgentRuntimeStatusView = AgentRuntimeStatusView & {
  badgeClass?: string;
};

/** 取该 Agent 的接入文档地址；没有文档时退回安装地址，都没有则返回 null。 */
export function getAgentGuideUrl(agent: AgentRuntimeItem): string | null {
  const docs = agent.docs_url?.trim();
  const install = agent.install_url?.trim();
  return docs || install || null;
}

/** 该 Agent 是否支持从平台内拉起登录；决定卡片是否显示「登录」按钮。 */
export function supportsAgentLogin(agent: AgentRuntimeItem): boolean {
  return Boolean(agent.can_login);
}

export function supportsAgentProbe(_agent: AgentRuntimeItem): boolean {
  return true;
}

/**
 * 把后端 / Rust 返回的原始字段收成 AgentRuntimeItem。
 *
 * 同时吃 snake_case 与 camelCase：上游字段风格不统一，在这里一次性抹平，
 * 上层就不必再判断两种命名。status 缺失时回落成「未安装」而不是抛错。
 */
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
    can_download: raw.can_download ?? raw.canDownload,
    status: {
      state: status?.state ?? "missing",
      label: status?.label ?? "未知",
      hint: status?.hint ?? null,
      badge_class: status?.badge_class ?? status?.badgeClass ?? "bg-muted text-muted-foreground",
    },
  };
}

/** 将 SQLite 偏好盖到 is_default / preferred_model_id。 */
export function applyAgentPreferences(
  agents: AgentRuntimeItem[],
  preferences: {
    default_agent_id?: string | null;
    default_models?: Record<string, string> | null;
  },
): AgentRuntimeItem[] {
  const preferredAgent = preferences.default_agent_id?.trim() || null;
  const hasModels = preferences.default_models != null;
  const models = preferences.default_models ?? {};
  return agents.map((agent) => ({
    ...agent,
    is_default: preferredAgent
      ? agent.id === preferredAgent && agent.available
      : Boolean(agent.is_default),
    // 未传入 default_models 时保留原 preferred_model_id，避免「设为默认」把模型打回第一项
    preferred_model_id: hasModels
      ? models[agent.id]?.trim() || null
      : (agent.preferred_model_id ?? null),
  }));
}

/**
 * 拉取本地 Agent 目录（Tauri PATH 探测）。
 * 若传入 apiBaseUrl，会再读 SQLite 偏好，并盖到 is_default / preferred_model_id。
 */
export async function listAgentRuntimes(
  apiBaseUrl?: string | null,
): Promise<AgentRuntimeItem[]> {
  if (!isTauri()) return [];

  const response = await invoke<AgentListResponse>("list_agent_runtimes_command");
  const agents = response.agents.map((agent) =>
    normalizeAgentRuntimeItem(agent as RawAgentRuntimeItem),
  );

  if (!apiBaseUrl) return agents;

  try {
    const preferences = await fetchAgentPreferences({ baseUrl: apiBaseUrl });
    return applyAgentPreferences(agents, preferences);
  } catch {
    return agents;
  }
}

/**
 * 仅取注册表占位（不扫 PATH），全部为「未安装」。
 * 用于尚未手动扫描、库中无缓存时的首屏展示。
 */
export async function listAgentRegistryPlaceholders(): Promise<AgentRuntimeItem[]> {
  if (!isTauri()) return [];
  const response = await invoke<AgentListResponse>("list_agent_registry_command");
  return response.agents.map((agent) =>
    normalizeAgentRuntimeItem(agent as RawAgentRuntimeItem),
  );
}

/** 根据探针鉴权结果组装统一鉴权视图（登录按钮 / 文档配置 API 共用）。 */
export function buildAuthView(
  agent: Pick<AgentRuntimeItem, "name" | "can_login">,
  authenticated: boolean | null,
): AgentRuntimeAuthView | null {
  const canLogin = Boolean(agent.can_login);
  if (authenticated === true) {
    return {
      state: "authenticated",
      label: "已登录",
      can_login: false,
    };
  }
  if (authenticated === false) {
    return {
      state: "unauthenticated",
      label: canLogin ? "未登录" : "未配置",
      can_login: canLogin,
      hint: canLogin
        ? `点击「登录」完成 ${agent.name} 授权`
        : "请在终端登录或配置 API Key，完成后点「扫描 Agent」",
    };
  }
  // 平台触发不了登录：不臆造「需配置」
  if (!canLogin) return null;
  return {
    state: "unknown",
    label: "未检测",
    can_login: canLogin,
    hint: "点击「扫描 Agent」查看登录状态",
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
      auth: null,
      models: null,
      status: {
        state: "missing",
        label: "未安装",
        hint:
          raw.error ??
          (agent.can_download
            ? "可点击「下载」安装到叮答托管目录"
            : "请按接入文档安装 CLI 后扫描"),
        badge_class: "bg-muted text-muted-foreground",
      },
    };
  }

  const authenticated = raw.authenticated ?? null;
  const auth = buildAuthView(agent, authenticated);
  const models = raw.models?.length ? raw.models : null;
  const hasLoginPath = Boolean(agent.can_login);

  const status: AgentRuntimeStatusView =
    authenticated === false
      ? {
          state: "auth_required",
          label: hasLoginPath ? "待登录" : "待配置",
          hint: auth?.hint ?? null,
          badge_class: "bg-amber-500/15 text-amber-700",
        }
      : hasLoginPath && authenticated == null
        ? {
            state: "auth_required",
            label: "待登录",
            hint: auth?.hint ?? null,
            badge_class: "bg-amber-500/15 text-amber-700",
          }
        : {
            state: "ready",
            label: "已就绪",
            hint: null,
            badge_class: "bg-emerald-500/15 text-emerald-600",
          };

  return {
    ...agent,
    available: true,
    command: raw.command ?? agent.command ?? null,
    source: raw.source ?? agent.source ?? null,
    version: raw.version ?? agent.version ?? null,
    auth,
    models,
    status,
  };
}

/**
 * 探测单个 Agent：桌面走 Tauri invoke；非桌面走 mock 分支（待移除，见文件头设计说明）。
 *
 * 无论成败都返回可渲染的 item：失败会转成「未安装 + 原因」，不抛错 ——
 * 一个 Agent 探测失败不应拖垮整轮并发探测。
 */
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
      authenticated: mockClaudeAuthenticated,
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

/**
 * 后台并行 probe 已安装的 Agent，按帧合并 onUpdate（避免每个 Agent 完成都触发订阅）。
 * 返回取消函数；全部结束后调用 onComplete。
 */
export function probeAgentsInBackground(
  agents: AgentRuntimeItem[],
  onUpdate: (agents: AgentRuntimeItem[]) => void,
  onComplete?: (agents: AgentRuntimeItem[]) => void,
): () => void {
  let cancelled = false;
  const targets = agents.filter((agent) => agent.available);
  if (targets.length === 0) {
    onComplete?.(agents);
    return () => undefined;
  }

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
    onComplete?.(snapshot);
  })();

  return () => {
    cancelled = true;
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  };
}

/**
 * 拉起 CLI 登录（桌面走 Tauri invoke，非桌面走 mock）。
 *
 * 不抛错：失败以 `started=false` + 给用户看的 message 返回，调用方直接展示即可。
 */
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
  if (agentId === "claude") {
    mockClaudeAuthenticated = true;
    return {
      started: true,
      message: "已调用 claude auth login（mock）。实际环境会在浏览器完成授权，完成后请点击「扫描 Agent」。",
    };
  }
  if (agentId !== "codex") {
    return { started: false, message: "该 Agent 暂不支持从平台登录" };
  }

  mockCodexAuthenticated = true;
  return {
    started: true,
    message: "已调用 codex login（mock）。实际环境会在浏览器中完成授权，完成后请点击「扫描 Agent」。",
  };
}

/** 下载结果：CLI 装到叮答托管目录后的绝对路径与版本。 */
export interface AgentDownloadResult {
  agentId: string;
  path: string;
  version?: string | null;
  message: string;
}

/** 下载到叮答托管目录（当前仅 OpenCode）。 */
export async function downloadAgentRuntime(agentId: string): Promise<AgentDownloadResult> {
  if (!isTauri()) {
    throw new Error("downloadAgentRuntime 仅在桌面端可用");
  }
  const raw = await invoke<{
    agentId?: string;
    agent_id?: string;
    path: string;
    version?: string | null;
    message: string;
  }>("download_agent_runtime", { agentId });

  return {
    agentId: raw.agentId ?? raw.agent_id ?? agentId,
    path: raw.path,
    version: raw.version ?? null,
    message: raw.message,
  };
}

export interface AgentRuntimeDownloadResult {
  agentId: string;
  path: string;
  version?: string | null;
  message: string;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
