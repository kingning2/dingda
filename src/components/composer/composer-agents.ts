import { useMemo } from "react";
import type { ComposerAgentOption } from "@/contracts/composer";
import type { AgentRuntimeItem } from "@/contracts/agent-runtime";
import { useDiscoveryStore } from "@/stores/discovery-store";

/** 自研产品 Agent 未开放前，不出现在输入框/设置里。 */
const HIDDEN_PRODUCT_AGENT_IDS = new Set(["dingda", "product"]);

function toComposerOptions(agents: AgentRuntimeItem[]): ComposerAgentOption[] {
  return agents
    .filter((agent) => agent.available && !HIDDEN_PRODUCT_AGENT_IDS.has(agent.id))
    .map((agent) => ({
      id: agent.id,
      name: agent.name,
      is_default: agent.is_default,
      preferred_model_id: agent.preferred_model_id ?? null,
      models: agent.models ?? [],
    }));
}

/** 已接入（PATH 可探测）的 Agent，供输入框选择。 */
export function getComposerAgentOptions(): ComposerAgentOption[] {
  return toComposerOptions(useDiscoveryStore.getState().agents);
}

export function resolveDefaultAgentId(agents: ComposerAgentOption[]): string | null {
  if (agents.length === 0) return null;
  return agents.find((agent) => agent.is_default)?.id ?? agents[0]?.id ?? null;
}

export function resolveModelId(
  agent: ComposerAgentOption | undefined,
  modelId: string | null,
): string | null {
  if (!agent?.models?.length) return null;
  if (modelId && agent.models.some((model) => model.id === modelId)) {
    return modelId;
  }
  const preferred = agent.preferred_model_id?.trim() || null;
  if (preferred && agent.models.some((model) => model.id === preferred)) {
    return preferred;
  }
  return agent.models[0]?.id ?? null;
}

export function resolveComposerSelection(
  agents: ComposerAgentOption[],
  agentId: string | null,
  modelId: string | null,
): { agentId: string | null; modelId: string | null } {
  const resolvedAgentId =
    agentId && agents.some((agent) => agent.id === agentId)
      ? agentId
      : resolveDefaultAgentId(agents);
  if (!resolvedAgentId) {
    return { agentId: null, modelId: null };
  }
  const agent = agents.find((item) => item.id === resolvedAgentId);
  return {
    agentId: resolvedAgentId,
    modelId: resolveModelId(agent, modelId),
  };
}

/** 订阅探测结果，输入框 Agent 列表随之更新。 */
export function useComposerAgentOptions(): ComposerAgentOption[] {
  // 必须先取稳定引用再 map：selector 里每次 new 数组会触发 Zustand 无限重渲染
  const agents = useDiscoveryStore((state) => state.agents);
  return useMemo(() => toComposerOptions(agents), [agents]);
}
