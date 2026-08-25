/**
 * 闲鱼商品监控 IPC。
 */

import { callRequest } from "./invoke";
import type { MonitorStepPayload } from "../events";

export interface MonitorTask {
  id: string;
  ownerId: number;
  name: string;
  intent: string;
  keywords: string[];
  accountId: string;
  aiAccountId: string;
  aiFailoverEnabled: boolean;
  aiAccountOrder: string[];
  intervalMinutes: number;
  enabled: boolean;
  /** 定时调度是否暂停（冻结剩余倒计时）。 */
  schedulePaused?: boolean;
  /** 暂停时冻结的剩余秒数。 */
  scheduleRemainingSecs?: number;
  /** 下次定时运行时间（RFC3339）。 */
  nextRunAt?: string;
  aiCriteria: string;
  maxResults: number;
  headed: boolean;
  isRunning: boolean;
  lastRunAt?: string;
  lastError?: string;
  createdAt: string;
  updatedAt: string;
}

export interface MonitorResult {
  id: string;
  taskId: string;
  ownerId: number;
  itemId: string;
  title: string;
  url: string;
  priceText: string;
  location: string;
  sellerName: string;
  aiRecommended: boolean;
  aiReason: string;
  notified: boolean;
  image?: string;
  crawledAt: string;
}

export interface MonitorRunSummary {
  scanned: number;
  newItems: number;
  skipped: number;
  recommended: number;
}

export function monitorTaskList(ownerId: number): Promise<MonitorTask[]> {
  return callRequest<MonitorTask[]>("monitor_task_list", { ownerId }).then((r) => r.data);
}

export function monitorTaskSave(params: {
  ownerId: number;
  id?: string;
  name: string;
  intent: string;
  keywords?: string[];
  accountId: string;
  aiAccountId: string;
  aiFailoverEnabled?: boolean;
  aiAccountOrder?: string[];
  intervalMinutes?: number;
  enabled?: boolean;
  aiCriteria: string;
  maxResults?: number;
  headed?: boolean;
}): Promise<MonitorTask> {
  return callRequest<MonitorTask>("monitor_task_save", {
    request: {
      owner_id: params.ownerId,
      id: params.id,
      name: params.name,
      intent: params.intent,
      keywords: params.keywords ?? [],
      account_id: params.accountId,
      ai_account_id: params.aiAccountId,
      ai_failover_enabled: params.aiFailoverEnabled ?? true,
      ai_account_order: params.aiAccountOrder ?? [],
      interval_minutes: params.intervalMinutes ?? 5,
      enabled: params.enabled ?? true,
      ai_criteria: params.aiCriteria,
      max_results: params.maxResults ?? 20,
      headed: params.headed ?? false,
    },
  }).then((r) => r.data);
}

export function monitorTaskDelete(ownerId: number, taskId: string): Promise<void> {
  return callRequest<void>("monitor_task_delete", {
    request: { owner_id: ownerId, task_id: taskId },
  }).then(() => undefined);
}

export function monitorTaskRun(ownerId: number, taskId: string): Promise<MonitorRunSummary> {
  return callRequest<MonitorRunSummary>("monitor_task_run", {
    request: { owner_id: ownerId, task_id: taskId },
  }).then((r) => r.data);
}

export function monitorTaskPauseSchedule(ownerId: number, taskId: string): Promise<MonitorTask> {
  return callRequest<MonitorTask>("monitor_task_pause_schedule", {
    request: { owner_id: ownerId, task_id: taskId },
  }).then((r) => r.data);
}

export function monitorTaskResumeSchedule(ownerId: number, taskId: string): Promise<MonitorTask> {
  return callRequest<MonitorTask>("monitor_task_resume_schedule", {
    request: { owner_id: ownerId, task_id: taskId },
  }).then((r) => r.data);
}

export function monitorResultList(ownerId: number, taskId: string): Promise<MonitorResult[]> {
  return callRequest<MonitorResult[]>("monitor_result_list", {
    request: { owner_id: ownerId, task_id: taskId },
  }).then((r) => r.data);
}

export interface MonitorRun {
  id: string;
  taskId: string;
  ownerId: number;
  status: "running" | "success" | "failed";
  startedAt: string;
  finishedAt?: string;
  error?: string;
  scanned: number;
  newItems: number;
  skipped: number;
  recommended: number;
  steps: MonitorStepPayload[];
}

export function monitorRunList(ownerId: number, taskId: string): Promise<MonitorRun[]> {
  return callRequest<MonitorRun[]>("monitor_run_list", {
    request: { owner_id: ownerId, task_id: taskId },
  }).then((r) => r.data);
}

export function monitorRunGet(ownerId: number, runId: string): Promise<MonitorRun | null> {
  return callRequest<MonitorRun | null>("monitor_run_get", {
    request: { owner_id: ownerId, run_id: runId },
  }).then((r) => r.data);
}

export interface MonitorStats {
  taskCount: number;
  runningCount: number;
  enabledCount: number;
  resultCount: number;
  recommendedCount: number;
  todayNewCount: number;
}

export function monitorStats(ownerId: number): Promise<MonitorStats> {
  return callRequest<MonitorStats>("monitor_stats", { ownerId }).then((r) => r.data);
}

export function monitorGenerateKeywords(params: {
  ownerId: number;
  intent: string;
  aiCriteria: string;
  aiAccountId: string;
  aiFailoverEnabled?: boolean;
  aiAccountOrder?: string[];
}): Promise<string[]> {
  return callRequest<{ keywords: string[] }>("monitor_generate_keywords", {
    request: {
      owner_id: params.ownerId,
      intent: params.intent,
      ai_criteria: params.aiCriteria,
      ai_account_id: params.aiAccountId,
      ai_failover_enabled: params.aiFailoverEnabled ?? true,
      ai_account_order: params.aiAccountOrder ?? [],
    },
  }).then((r) => r.data.keywords);
}
