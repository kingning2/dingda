import type { AgentWorkDetailView, AgentWorkProductItem, AgentWorkStepView } from "@/contracts/ai-work";

export function findWorkStep(detail: AgentWorkDetailView, stepId: string): AgentWorkStepView | null {
  for (const message of detail.messages) {
    const step = message.steps?.find((item) => item.id === stepId);
    if (step) return step;
  }
  return null;
}

/** 从步骤关联的浏览帧解析页面 URL（用于对话内跳转）。 */
export function resolveStepPageUrl(detail: AgentWorkDetailView, step: AgentWorkStepView): string | null {
  if (!step.browser_frame_id) return null;

  if (detail.browser_live.frame_id === step.browser_frame_id) {
    const url = detail.browser_live.url;
    return url && url !== "about:blank" ? url : null;
  }

  const frame = detail.browser_history.find((item) => item.id === step.browser_frame_id);
  return frame?.url ?? null;
}

export function productsForStep(
  items: AgentWorkProductItem[],
  stepId: string | null,
): AgentWorkProductItem[] {
  if (!stepId) return items;
  return items.filter((item) => item.step_id === stepId);
}

export function stepHasProducts(items: AgentWorkProductItem[], stepId: string): boolean {
  return items.some((item) => item.step_id === stepId);
}

export function groupProductsByStep(
  items: AgentWorkProductItem[],
): Array<{ stepId: string; stepLabel: string; items: AgentWorkProductItem[] }> {
  const groups = new Map<string, { stepLabel: string; items: AgentWorkProductItem[] }>();

  for (const item of items) {
    const existing = groups.get(item.step_id);
    if (existing) {
      existing.items.push(item);
      continue;
    }
    groups.set(item.step_id, {
      stepLabel: item.step_label ?? item.step_id,
      items: [item],
    });
  }

  return Array.from(groups.entries()).map(([stepId, group]) => ({
    stepId,
    stepLabel: group.stepLabel,
    items: group.items,
  }));
}
