import { useMemo } from "react";

/**
 * Composer 的 Agent 选项。
 *
 * 外部 CLI Agent 已移除，产品只剩内置 dingda：不出列表、不发选项，
 * 发送时 agent_id 固定为 "dingda"。
 */

/** 产品 Agent 固定 id（与后端 run_work 的 runtime_id 对齐）。 */
export const PRODUCT_AGENT_ID = "dingda";

/** 已接入（PATH 可探测）的 Agent，供输入框选择。外部 CLI 移除后恒为空。 */
export function getComposerAgentOptions(): [] {
  return [];
}

export function resolveDefaultAgentId(_agents: unknown[]): string {
  void _agents;
  return PRODUCT_AGENT_ID;
}

export function resolveComposerSelection(
  _agents: unknown[],
  _agentId: string | null,
  _modelId: string | null,
): { agentId: string; modelId: null } {
  return { agentId: PRODUCT_AGENT_ID, modelId: null };
}

/** 订阅探测结果，输入框 Agent 列表随之更新。外部 CLI 移除后恒为空。 */
export function useComposerAgentOptions(): [] {
  return useMemo(() => [], []);
}
