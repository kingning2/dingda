import type { MonitorProgressPayload, MonitorStepPayload } from "@desk/platform/events";
import type { MonitorRun } from "@desk/platform/ipc/xianyu-monitor";

/** 步骤稳定 key — 优先 stepId，否则用 stage + index + message 前缀。 */
export function monitorStepKey(step: MonitorStepPayload, index: number): string {
  return step.stepId ?? `${step.stage}-${index}-${step.message.slice(0, 48)}`;
}

function hasStep(run: MonitorRun, payload: MonitorProgressPayload): boolean {
  if (payload.stepId) {
    return run.steps.some((step) => step.stepId === payload.stepId);
  }
  const last = run.steps[run.steps.length - 1];
  if (!last) return false;
  return (
    last.stage === payload.stage &&
    last.message === payload.message &&
    last.role === payload.role
  );
}

/** 增量追加单步 — 不替换已有 steps 数组。 */
export function appendMonitorStep(run: MonitorRun, payload: MonitorProgressPayload): MonitorRun {
  if (hasStep(run, payload)) {
    return run;
  }
  const step: MonitorStepPayload = {
    stepId: payload.stepId,
    runId: payload.runId,
    taskId: payload.taskId,
    taskName: payload.taskName,
    stage: payload.stage,
    message: payload.message,
    detail: payload.detail,
    summary: payload.summary,
    content: payload.content,
    contentKind: payload.contentKind,
    role: payload.role,
  };
  return { ...run, steps: [...run.steps, step] };
}

/** 根据流式进度事件更新运行元数据 + 追加步骤。 */
export function patchMonitorRunFromProgress(
  run: MonitorRun,
  payload: MonitorProgressPayload,
): MonitorRun {
  let next = appendMonitorStep(run, payload);

  if (payload.stage === "finished") {
    next = {
      ...next,
      status: "success",
      finishedAt: next.finishedAt ?? new Date().toISOString(),
      scanned: payload.summary?.scanned ?? next.scanned,
      newItems: payload.summary?.newItems ?? next.newItems,
      skipped: payload.summary?.skipped ?? next.skipped,
      recommended: payload.summary?.recommended ?? next.recommended,
    };
  } else if (payload.stage === "failed") {
    next = {
      ...next,
      status: "failed",
      error: payload.detail ?? next.error,
      finishedAt: next.finishedAt ?? new Date().toISOString(),
    };
  } else if (payload.stage === "started") {
    next = { ...next, status: "running" };
  }

  return next;
}
