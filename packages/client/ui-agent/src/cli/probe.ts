/**
 * Agent 探测：单个 probe、后台批量 probe、探测状态标记。
 *
 * 职责：
 *   - `probeAgentRuntime`：探测单个 Agent，无论成败都返回可渲染的 item。
 *   - `probeAgentsInBackground`：后台并行 probe，按帧合并更新。
 *   - `markAgentsProbing`：把指定 Agent 标成「检测中」。
 */

import type {
  AgentRuntimeItem,
  AgentRuntimeProbeResult,
  AgentRuntimeStatusView,
} from "@v2/contracts/agent-runtime";
import { supportsExternalAgents } from "@v2/runtime/capabilities";
import { STATUS_TONE } from "../status-tone";
import { buildAuthView } from "./auth-view";

function mergeProbeResult(
  agent: AgentRuntimeItem,
  raw: AgentRuntimeProbeResult,
): AgentRuntimeItem {
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
        badge_class: STATUS_TONE.neutral,
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
          badge_class: STATUS_TONE.pending,
        }
      : hasLoginPath && authenticated == null
        ? {
            state: "auth_required",
            label: "待登录",
            hint: auth?.hint ?? null,
            badge_class: STATUS_TONE.pending,
          }
        : {
            state: "ready",
            label: "已就绪",
            hint: null,
            badge_class: STATUS_TONE.ready,
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
 * 探测单个 Agent（桌面走 Tauri invoke）。
 *
 * 无论成败都返回可渲染的 item：失败会转成「未安装 + 原因」，不抛错 ——
 * 一个 Agent 探测失败不应拖垮整轮并发探测。
 */
export async function probeAgentRuntime(agent: AgentRuntimeItem): Promise<AgentRuntimeItem> {
  if (!supportsExternalAgents()) return agent;

  const { invoke } = await import("@tauri-apps/api/core");
  try {
    const raw = await invoke<AgentRuntimeProbeResult>("probe_agent_runtime", {
      agentId: agent.id,
    });
    return mergeProbeResult(agent, raw);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return mergeProbeResult(agent, { available: false, error: message });
  }
}

const PROBING_STATUS: AgentRuntimeStatusView = {
  state: "probing",
  label: "检测中…",
  hint: null,
  badge_class: STATUS_TONE.active,
};

/** 把指定的一批 Agent 标成「检测中」—— 探测开始前先给 UI 反馈。 */
export function markAgentsProbing(
  agents: AgentRuntimeItem[],
  agentIds: Set<string>,
): AgentRuntimeItem[] {
  return agents.map((agent) =>
    agentIds.has(agent.id) ? { ...agent, status: PROBING_STATUS } : agent,
  );
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
