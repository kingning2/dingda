/**
 * 任务副驾 agent — HttpAgent 子类，run 时注入任务上下文快照与 AI 账号凭据。
 *
 * 直连链路（CHG-20260829-007）：CopilotKit → sidecar `/v1/copilot/agui` SSE；
 * `forwardedProps.default_*` 仅存在于本机回环连接。
 */

import type { RunAgentInput } from "@ag-ui/client";
import { HttpAgent } from "@copilotkit/react-core/v2";

/** run 时注入的上下文（state=任务快照；forwardedProps=AI 凭据）。 */
export interface TaskCopilotContext {
  state?: Record<string, unknown>;
  forwardedProps?: Record<string, unknown>;
}

export const TASK_COPILOT_AGENT_ID = "task_copilot";

export class TaskCopilotAgent extends HttpAgent {
  private readonly getContext: () => TaskCopilotContext;

  constructor(
    config: ConstructorParameters<typeof HttpAgent>[0],
    getContext: () => TaskCopilotContext,
  ) {
    super(config);
    this.getContext = getContext;
  }

  override run(input: RunAgentInput) {
    const context = this.getContext();
    return super.run({
      ...input,
      state: { ...(input.state ?? {}), ...(context.state ?? {}) },
      forwardedProps: { ...(input.forwardedProps ?? {}), ...(context.forwardedProps ?? {}) },
    });
  }
}
