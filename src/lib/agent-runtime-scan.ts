import { isTauri } from "@tauri-apps/api/core";
import type { AgentRuntimeItem } from "@/contracts/agent-runtime";
import {
  listAgentRuntimes,
  mergeListDetection,
  probeAgentsInBackground,
} from "@/lib/agent-runtime";
import {
  getAgentRuntimes,
  mockRescanAgentRuntimes,
  setAgentRuntimes,
} from "@/components/agent/agent-mock-data";

let initialScanStarted = false;
let cancelBackgroundProbe: (() => void) | null = null;

function commitAgents(next: AgentRuntimeItem[]) {
  setAgentRuntimes(next);
}

function startBackgroundProbe(agents: AgentRuntimeItem[]) {
  cancelBackgroundProbe?.();
  cancelBackgroundProbe = probeAgentsInBackground(agents, commitAgents);
}

/** 应用启动后仅执行一次的 PATH 检测 + 后台 probe。 */
export async function ensureAgentRuntimesScanned(): Promise<void> {
  if (initialScanStarted) return;
  initialScanStarted = true;

  if (!isTauri()) return;

  const base = getAgentRuntimes();
  const detected = await listAgentRuntimes();
  const merged = mergeListDetection(base, detected);
  commitAgents(merged);
  startBackgroundProbe(merged);
}

/** 用户手动点击「扫描 Agent」时调用。 */
export async function rescanAgentRuntimes(): Promise<AgentRuntimeItem[]> {
  if (!isTauri()) {
    await new Promise((resolve) => window.setTimeout(resolve, 600));
    const next = mockRescanAgentRuntimes(getAgentRuntimes());
    commitAgents(next);
    return next;
  }

  const detected = await listAgentRuntimes();
  const merged = mergeListDetection(getAgentRuntimes(), detected);
  commitAgents(merged);
  startBackgroundProbe(merged);
  return merged;
}

export function probeSingleAgent(agentId: string) {
  cancelBackgroundProbe?.();
  cancelBackgroundProbe = probeAgentsInBackground(
    markSingleProbing(getAgentRuntimes(), agentId),
    commitAgents,
  );
}

function markSingleProbing(agents: AgentRuntimeItem[], agentId: string): AgentRuntimeItem[] {
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
