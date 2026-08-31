/**
 * 任务中心 — 三栏：历史 | 对话+执行过程 | 结构化分析。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import { agentRunList, type AgentRunRecord } from "@desk/platform/ipc/agent-run";

import { useWorkspaceNav } from "../../app/use-workspace-tabs";
import { pageStyles as layout } from "./layout/styles";
import { progressLabel } from "./price-compare";
import { useAgentRun } from "./use-agent-run";
import { ChatPanel } from "./chat/panel";
import { ChatProvider, useStartNewChat, useTaskContext } from "./chat/provider";
import { registerRunStarted } from "./chat/run-nav";
import { useChat } from "./chat/use-chat";
import { HistoryPanel } from "./list/panel";
import { ResultsPanel } from "./results/panel";

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

function TasksPageShell() {
  const { taskId } = useParams();
  const { selectTab } = useWorkspaceNav();
  const { record, thoughts, isActive, crawlCounts } = useAgentRun(taskId);
  const tasks = useTaskListSnapshot();
  const startNewChat = useStartNewChat();
  const { syncTaskSession, upsertRunReply, upsertRunThoughts } = useChat();

  const handleNewChat = useCallback(() => {
    startNewChat();
    selectTab("/tasks");
  }, [selectTab, startNewChat]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "j") {
        event.preventDefault();
        handleNewChat();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleNewChat]);

  useEffect(() => {
    return registerRunStarted((runId) => {
      selectTab(`/tasks/${runId}`);
    });
  }, [selectTab]);

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

  useTaskContext(snapshotState);

  useEffect(() => {
    if (!taskId) {
      syncTaskSession(undefined);
      return;
    }
    if (!record) {
      return;
    }
    syncTaskSession(taskId, {
      user: record.user,
      reply: record.reply,
      error: record.error,
    });
  }, [taskId, record, syncTaskSession]);

  useEffect(() => {
    if (!taskId || !record?.reply) {
      return;
    }
    upsertRunReply(record.reply);
  }, [taskId, record?.reply, upsertRunReply]);

  useEffect(() => {
    if (!taskId || thoughts.length === 0) {
      return;
    }
    upsertRunThoughts(thoughts);
  }, [taskId, thoughts, upsertRunThoughts]);

  const finalizeStep = record?.steps.find((step) => step.node === "finalize");
  const replyText =
    record?.reply ||
    (finalizeStep?.status === "running" ? finalizeStep.content : undefined);

  const chatTitle = record?.user || (taskId ? "任务分析" : "新对话");
  const chatSubtitle = taskId && record ? progressLabel(record) : undefined;

  return (
    <div style={layout.shell}>
      <HistoryPanel activeTaskId={taskId} onNewChat={handleNewChat} />

      <div style={layout.chatColumn}>
        <header style={layout.chatHeader}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <h1 style={layout.chatTitle}>{chatTitle}</h1>
            {chatSubtitle ? <p style={layout.chatSubtitle}>{chatSubtitle}</p> : null}
          </div>
        </header>
        <ChatPanel />
      </div>

      <ResultsPanel
        record={taskId ? record : null}
        replyText={replyText}
        replyStreaming={!record?.reply && Boolean(isActive)}
        productCount={crawlCounts?.crawled}
      />
    </div>
  );
}

export function TasksChatRoute() {
  return (
    <ChatProvider>
      <TasksPageShell />
    </ChatProvider>
  );
}
