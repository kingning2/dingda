import { listenEvent } from "./index";

export const AGENT_PROGRESS_EVENT = "app/agent/progress";

export interface AgentProgressPayload {
  category?: string;
  runId: string;
  stepId?: string;
  node?: string;
  index?: number;
  total?: number;
  status: string;
  message: string;
  detail?: string;
  errorKind?: string;
  accountId?: string;
  model?: string;
  content?: string;
}

export function listenAgentProgress(
  handler: (payload: AgentProgressPayload) => void,
) {
  return listenEvent<AgentProgressPayload>(AGENT_PROGRESS_EVENT, handler);
}
