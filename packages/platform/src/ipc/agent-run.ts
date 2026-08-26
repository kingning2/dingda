/**
 * Agent run IPC — 经 AgentRuntime 的可控 graph 编排。
 */

import { call } from "./invoke";

export interface AgentRunStep {
  id: string;
  node: string;
  index: number;
  status: string;
  label?: string;
  detail?: string;
  errorKind?: string;
  accountId?: string;
  model?: string;
  content?: string;
}

export interface AgentRunRecord {
  id: string;
  kind: string;
  state: string;
  user: string;
  reply?: string;
  error?: string;
  errorKind?: string;
  failedNode?: string;
  steps: AgentRunStep[];
  createdAt: number;
  updatedAt: number;
  finishedAt?: number;
}

export function agentRunStart(params: {
  user: string;
  system?: string;
  resumeFromRunId?: string;
  resumeNode?: string;
}): Promise<AgentRunRecord> {
  return call<AgentRunRecord>("agent_run_start", {
    request: {
      user: params.user,
      system: params.system,
      resumeFromRunId: params.resumeFromRunId,
      resumeNode: params.resumeNode,
    },
  });
}

export function agentRunPause(runId?: string): Promise<AgentRunRecord> {
  return call<AgentRunRecord>("agent_run_pause", { request: { runId } });
}

export function agentRunResume(params: {
  runId?: string;
  mode: "continue" | "restart" | "seek";
  node?: string;
}): Promise<AgentRunRecord> {
  return call<AgentRunRecord>("agent_run_resume", {
    request: {
      runId: params.runId,
      mode: params.mode,
      node: params.node,
    },
  });
}

export function agentRunCancel(runId?: string): Promise<AgentRunRecord> {
  return call<AgentRunRecord>("agent_run_cancel", { request: { runId } });
}

export function agentRunStatus(runId?: string): Promise<AgentRunRecord> {
  return call<AgentRunRecord>("agent_run_status", { request: { runId } });
}

export function agentRunGet(runId?: string): Promise<AgentRunRecord> {
  return call<AgentRunRecord>("agent_run_get", { request: { runId } });
}

export function agentRunList(): Promise<AgentRunRecord[]> {
  return call<AgentRunRecord[]>("agent_run_list");
}
