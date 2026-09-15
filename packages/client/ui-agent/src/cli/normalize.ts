/**
 * 把后端 / Rust 返回的原始字段规整成 `AgentRuntimeItem`。
 *
 * 职责：
 *   - snake_case 与 camelCase 风格抹平（Rust 侧用 `#[serde(rename_all = "camelCase")]`）。
 *   - 将 SQLite 偏好盖到 `is_default` / `preferred_model_id`。
 *
 * 设计说明：
 *   `Raw*` 类型保留了 camelCase 别名 —— 这不是冗余，是**两条上游的风格差异**
 *   （Rust 发 camelCase，Python / SQLite / contracts 用 snake_case）。
 */

import type {
  AgentRuntimeItem,
  AgentRuntimeStatusView,
} from "@v2/contracts/agent-runtime";
import { STATUS_TONE } from "../status-tone";

/** Rust 侧下发的原始 item（含 camelCase 别名）。 */
export type RawAgentRuntimeItem = AgentRuntimeItem & {
  installUrl?: string | null;
  docsUrl?: string | null;
  isDefault?: boolean;
  externalMcpInjection?: string | null;
  canLogin?: boolean;
  canProbe?: boolean;
  canDownload?: boolean;
  status?: RawAgentRuntimeStatusView;
};

type RawAgentRuntimeStatusView = AgentRuntimeStatusView & {
  badgeClass?: string;
};

/** 下载结果：CLI 装到托管目录后的绝对路径与版本。 */
export interface AgentDownloadResult {
  agentId: string;
  path: string;
  version?: string | null;
  message: string;
}

/**
 * 把原始字段收成 `AgentRuntimeItem`。
 *
 * snake_case 与 camelCase 都吃，在这里一次性抹平。
 * status 缺失时回落成「未安装」而不是抛错。
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
    external_mcp_injection:
      raw.external_mcp_injection ?? raw.externalMcpInjection ?? null,
    auth: raw.auth ?? null,
    models: raw.models ?? null,
    can_login: raw.can_login ?? raw.canLogin,
    can_probe: raw.can_probe ?? raw.canProbe,
    can_download: raw.can_download ?? raw.canDownload,
    status: {
      state: status?.state ?? "missing",
      label: status?.label ?? "未知",
      hint: status?.hint ?? null,
      badge_class: status?.badge_class ?? status?.badgeClass ?? STATUS_TONE.neutral,
    },
  };
}

/** 将 SQLite 偏好盖到 `is_default` / `preferred_model_id`。 */
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
    preferred_model_id: hasModels
      ? models[agent.id]?.trim() || null
      : (agent.preferred_model_id ?? null),
  }));
}
