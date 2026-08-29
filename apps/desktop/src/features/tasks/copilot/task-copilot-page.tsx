/**
 * 任务副驾页 — 对话流为主体（CHG-20260829-007 布局决策）。
 *
 * /tasks/copilot：新建会话（可问答、发起新任务）。
 * /tasks/:taskId：绑定 run 的会话，顶部实时任务条由 useAgentRun 事件驱动；
 * 任务上下文快照经 state 注入 Python 副驾（Python 不落盘、不做文件操作）。
 */

import "@copilotkit/react-core/v2/styles.css";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import { CopilotChat } from "@copilotkit/react-core/v2";
import { agentRunList, type AgentRunRecord } from "@desk/platform/ipc/agent-run";
import { PageScaffold } from "@desk/ui";

import { stateLabel, progressLabel } from "../price-compare";
import { useAgentRun } from "../use-agent-run";
import { TaskCopilotProvider, useCopilotTaskContext } from "./task-copilot-provider";

/** 任务列表快照：轮询刷新，注入副驾 state.tasks。 */
function useTaskListSnapshot(): AgentRunRecord[] {
  const [runs, setRuns] = useState<AgentRunRecord[]>([]);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      void agentRunList().then((list) => {
        if (!cancelled) {
          setRuns(list);
        }
      });
    };
    load();
    const timer = window.setInterval(load, 5_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return runs;
}

interface RunStatusBarProps {
  record: AgentRunRecord | null;
}

/** 实时任务条：对话流上方的运行态摘要（进度事件实时驱动）。 */
function RunStatusBar({ record }: RunStatusBarProps) {
  if (!record) {
    return null;
  }
  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-border/60 bg-card px-4 py-2 text-[length:var(--text-xs)]">
      <span className="font-medium text-foreground">#{record.id.slice(0, 8)}</span>
      <span className="text-muted-foreground">{stateLabel(record.state)}</span>
      <span className="text-muted-foreground">{progressLabel(record)}</span>
      {record.reply ? (
        <span className="min-w-0 flex-1 truncate text-muted-foreground">结论：{record.reply}</span>
      ) : null}
    </div>
  );
}

/** 副驾聊天主体（须处于 TaskCopilotProvider 内）。 */
function TaskCopilotChat() {
  const { taskId } = useParams();
  const { record } = useAgentRun(taskId);
  const tasks = useTaskListSnapshot();

  const snapshotState = useMemo(
    () => ({
      tasks: tasks.slice(0, 20).map((item) => ({
        run_id: item.id,
        kind: item.kind,
        state: item.state,
        progress: progressLabel(item),
        query: item.user,
        updated_at: item.updatedAt,
      })),
      current_run: record
        ? {
            run_id: record.id,
            state: record.state,
            query: record.user,
            reply: record.reply,
            steps: record.steps.map((step) => ({
              node: step.node,
              status: step.status,
              label: step.label,
              content: step.content?.slice(0, 2_000),
            })),
          }
        : undefined,
    }),
    [tasks, record],
  );

  useCopilotTaskContext(snapshotState);

  return (
    <PageScaffold
      title="AI 副驾"
      subtitle={taskId ? "绑定当前任务的对话助手" : "管理比价任务：查询进度、发起任务、解读结论"}
      scroll={false}
      containerPadding="none"
    >
      {taskId ? <RunStatusBar record={record} /> : null}
      <div className="copilot-chat-surface min-h-0 flex-1 overflow-hidden [&_form]:border-0">
        <CopilotChat
          agentId="task_copilot"
          labels={{ chatInputPlaceholder: "询问任务进度、发起比价…" }}
        />
      </div>
    </PageScaffold>
  );
}

/** 路由入口：Provider + 对话页。 */
export function TaskCopilotRoute() {
  return (
    <TaskCopilotProvider>
      <TaskCopilotChat />
    </TaskCopilotProvider>
  );
}
