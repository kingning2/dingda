import { useEffect, useState } from "react";
import type { ComposerAgentOption } from "@/contracts/composer";
import { getAgentRuntimes, subscribeAgentRuntimes } from "@/components/agent/agent-mock-data";

/** 已接入（PATH 可探测）的 Agent，供输入框选择。 */
export function getComposerAgentOptions(): ComposerAgentOption[] {
  return getAgentRuntimes()
    .filter((agent) => agent.available)
    .map((agent) => ({
      id: agent.id,
      name: agent.name,
      is_default: agent.is_default,
      models: agent.models ?? [],
    }));
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

function composerAgentOptionsEqual(
  prev: ComposerAgentOption[],
  next: ComposerAgentOption[],
): boolean {
  if (prev.length !== next.length) return false;
  return prev.every((agent, index) => {
    const other = next[index];
    if (!other) return false;
    if (
      agent.id !== other.id ||
      agent.name !== other.name ||
      agent.is_default !== other.is_default
    ) {
      return false;
    }
    const prevModels = agent.models ?? [];
    const nextModels = other.models ?? [];
    if (prevModels.length !== nextModels.length) return false;
    return prevModels.every(
      (model, modelIndex) =>
        model.id === nextModels[modelIndex]?.id &&
        model.label === nextModels[modelIndex]?.label,
    );
  });
}

/** 订阅接入页扫描结果，输入框 Agent 列表会随之更新。 */
export function useComposerAgentOptions(): ComposerAgentOption[] {
  const [agents, setAgents] = useState(getComposerAgentOptions);

  useEffect(() => {
    return subscribeAgentRuntimes(() => {
      const next = getComposerAgentOptions();
      setAgents((prev) => (composerAgentOptionsEqual(prev, next) ? prev : next));
    });
  }, []);

  return agents;
}
