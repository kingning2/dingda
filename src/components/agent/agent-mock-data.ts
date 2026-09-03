import type {
  AgentRuntimeAuthView,
  AgentRuntimeItem,
  AgentRuntimeModelView,
  AgentRuntimeStatusView,
} from "@/contracts/agent-runtime";
import { isTauri } from "@tauri-apps/api/core";
import { buildAuthView } from "@/lib/agent-runtime";
import { AGENT_CATALOG } from "./agent-catalog";

const AGENT_READY = {
  state: "ready",
  label: "已就绪",
  hint: null,
  badge_class: "bg-emerald-500/15 text-emerald-600",
};

const AGENT_MISSING = {
  state: "missing",
  label: "未安装",
  hint: "请按官方文档安装后点击「扫描 Agent」",
  badge_class: "bg-muted text-muted-foreground",
};

/** mock：浏览器预览默认 Codex + Claude 已安装；Tauri 下先展示静态目录，等后端 PATH 探测后再更新。 */
const MOCK_INSTALLED_IDS = new Set(isTauri() ? [] : ["codex", "claude"]);

const MOCK_COMMAND: Record<string, string> = {
  codex: "codex",
  claude: "claude",
  "cursor-agent": "agent",
};

const MOCK_VERSION: Record<string, string> = {
  codex: "0.34.0",
  claude: "1.0.88",
};

function buildMockAgent(entry: (typeof AGENT_CATALOG)[number]): AgentRuntimeItem {
  const available = MOCK_INSTALLED_IDS.has(entry.id);
  const auth = available && entry.id === "codex" ? buildAuthView(entry.id, false) : null;
  const codexStatus =
    entry.id === "codex" && available
      ? {
          state: "auth_required",
          label: "待登录",
          hint: "请先登录 Codex CLI",
          badge_class: "bg-amber-500/15 text-amber-700",
        }
      : available
        ? AGENT_READY
        : AGENT_MISSING;

  return {
    id: entry.id,
    name: entry.name,
    description: entry.description,
    available,
    version: available ? (MOCK_VERSION[entry.id] ?? null) : null,
    command: available ? (MOCK_COMMAND[entry.id] ?? entry.id) : null,
    install_url: entry.install_url,
    docs_url: entry.docs_url,
    is_default: entry.id === "codex",
    external_mcp_injection: entry.external_mcp_injection ?? null,
    auth,
    models: null,
    can_login: entry.id === "codex",
    can_probe: true,
    status: codexStatus,
  };
}

function createInitialAgentRuntimes(): AgentRuntimeItem[] {
  return AGENT_CATALOG.map(buildMockAgent);
}

type AgentRuntimeListener = () => void;
const agentRuntimeListeners = new Set<AgentRuntimeListener>();

function notifyAgentRuntimeListeners(): void {
  agentRuntimeListeners.forEach((listener) => listener());
}

let agentRuntimeSnapshot: AgentRuntimeItem[] = createInitialAgentRuntimes();

function statusEqual(a: AgentRuntimeStatusView, b: AgentRuntimeStatusView): boolean {
  return (
    a.state === b.state &&
    a.label === b.label &&
    a.hint === b.hint &&
    a.badge_class === b.badge_class
  );
}

function authEqual(
  a: AgentRuntimeAuthView | null | undefined,
  b: AgentRuntimeAuthView | null | undefined,
): boolean {
  if (a === b) return true;
  if (!a || !b) return !a && !b;
  return (
    a.state === b.state &&
    a.label === b.label &&
    a.hint === b.hint &&
    a.can_login === b.can_login
  );
}

function modelsEqual(
  a: AgentRuntimeModelView[] | null | undefined,
  b: AgentRuntimeModelView[] | null | undefined,
): boolean {
  if (a === b) return true;
  if (!a || !b) return !a && !b;
  if (a.length !== b.length) return false;
  return a.every((model, index) => {
    const other = b[index];
    return model.id === other?.id && model.label === other?.label;
  });
}

function agentRuntimeEqual(a: AgentRuntimeItem, b: AgentRuntimeItem): boolean {
  return (
    a.id === b.id &&
    a.available === b.available &&
    a.version === b.version &&
    a.command === b.command &&
    a.is_default === b.is_default &&
    a.can_login === b.can_login &&
    a.can_probe === b.can_probe &&
    statusEqual(a.status, b.status) &&
    authEqual(a.auth, b.auth) &&
    modelsEqual(a.models, b.models)
  );
}

function agentRuntimesEqual(prev: AgentRuntimeItem[], next: AgentRuntimeItem[]): boolean {
  if (prev.length !== next.length) return false;
  return prev.every((agent, index) => agentRuntimeEqual(agent, next[index]!));
}

export function getAgentRuntimes(): AgentRuntimeItem[] {
  return agentRuntimeSnapshot;
}

export function setAgentRuntimes(agents: AgentRuntimeItem[]): void {
  if (agentRuntimesEqual(agentRuntimeSnapshot, agents)) return;
  agentRuntimeSnapshot = agents;
  notifyAgentRuntimeListeners();
}

export function areAgentRuntimesEqual(prev: AgentRuntimeItem[], next: AgentRuntimeItem[]): boolean {
  return agentRuntimesEqual(prev, next);
}

export function subscribeAgentRuntimes(listener: AgentRuntimeListener): () => void {
  agentRuntimeListeners.add(listener);
  return () => agentRuntimeListeners.delete(listener);
}

export function mockRescanAgentRuntimes(current: AgentRuntimeItem[]): AgentRuntimeItem[] {
  return current.map((agent) => {
    if (agent.id === "cursor-agent") {
      return {
        ...agent,
        available: true,
        version: "2026.09.01",
        command: "agent",
        status: AGENT_READY,
      };
    }
    return agent;
  });
}

export function mockSetDefaultAgent(
  agents: AgentRuntimeItem[],
  agentId: string,
): AgentRuntimeItem[] {
  return agents.map((agent) => ({
    ...agent,
    is_default: agent.id === agentId && agent.available,
  }));
}
