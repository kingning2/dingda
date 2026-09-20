import type { ComposerAgentOption } from "@v2/contracts/composer";

/** 已接入的 Agent，供输入框选择。 */
export function getComposerAgentOptions(): ComposerAgentOption[] {
  return [];
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

/** 空列表常量：多个组件同时订阅时保持引用稳定，避免无谓重渲染。 */
const NO_AGENTS: ComposerAgentOption[] = [];

/** 订阅探测结果，输入框 Agent 列表随之更新。 */
export function useComposerAgentOptions(): ComposerAgentOption[] {
  return NO_AGENTS;
}
