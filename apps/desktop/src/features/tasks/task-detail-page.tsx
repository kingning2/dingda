/**
 * 任务详情 — 真实 AgentRun 进度 / 步骤详情 / 控制。
 */

import { useEffect, useRef } from "react";
import { useParams } from "react-router";
import {
  AgentThinking,
  Button,
  CrawlerProgress,
  PageScaffold,
  TypewriterText,
} from "@desk/ui";
import { SectionEmpty } from "@components/product-shell";
import { useWorkspaceNav } from "../../app/use-workspace-tabs";
import { stateLabel } from "./price-compare";
import { useAgentRun, type RunLogLine } from "./use-agent-run";

function RunLog({ lines }: { lines: RunLogLine[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [lines]);
  return (
    <div className="flex h-72 flex-col overflow-hidden rounded-[var(--radius-xl)] border border-border/70 bg-card shadow-sm">
      <div className="border-b border-border/60 px-3 py-2">
        <h3 className="text-[length:var(--text-sm)] font-medium text-foreground">过程记录</h3>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {lines.length === 0 ? (
          <p className="text-[length:var(--text-xs)] text-muted-foreground">暂无日志</p>
        ) : (
          <ul className="space-y-1.5">
            {lines.map((line) => (
              <li
                key={line.id}
                className="whitespace-pre-wrap break-words text-[length:var(--text-xs)] text-muted-foreground"
              >
                <TypewriterText text={line.text} streaming={Boolean(line.streaming)} />
              </li>
            ))}
          </ul>
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}

/** 任务详情：条件 / 进度 / 结果入口。 */
export function TaskDetailPage() {
  const { taskId } = useParams();
  const { selectTab } = useWorkspaceNav();
  const {
    record,
    error,
    loading,
    busy,
    logLines,
    thoughts,
    progressPercent,
    crawlCounts,
    statusMessage,
    isActive,
    pause,
    resume,
    cancel,
    restart,
  } = useAgentRun(taskId);

  if (loading) {
    return (
      <PageScaffold title="任务详情" subtitle={taskId ?? ""} ambient="none" containerPadding="sm">
        <p className="text-[length:var(--text-sm)] text-muted-foreground">加载中…</p>
      </PageScaffold>
    );
  }

  if (!record) {
    return (
      <PageScaffold title="任务详情" subtitle={taskId ?? ""} ambient="none" containerPadding="sm">
        <SectionEmpty
          title="未找到任务"
          description={error ?? "请从任务中心发起比价任务。"}
        />
        <div className="mt-4">
          <Button type="button" size="sm" variant="outline" onClick={() => selectTab("/tasks")}>
            返回任务中心
          </Button>
        </div>
      </PageScaffold>
    );
  }

  const crawlRunning = record.steps.some(
    (step) => step.node === "crawl" && step.status === "running",
  );
  const finalizeStep = record.steps.find((step) => step.node === "finalize");
  const replyText =
    record.reply ||
    (finalizeStep?.status === "running" ? finalizeStep.content : undefined);

  return (
    <PageScaffold
      title="任务详情"
      subtitle={record.user}
      ambient="none"
      containerPadding="sm"
      extra={
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[length:var(--text-xs)] text-muted-foreground">
            {stateLabel(record.state)}
          </span>
          {record.state === "running" || record.state === "waiting_network" ? (
            <Button type="button" size="sm" variant="outline" disabled={busy} onClick={pause}>
              暂停
            </Button>
          ) : null}
          {record.state === "paused" ? (
            <Button type="button" size="sm" variant="outline" disabled={busy} onClick={resume}>
              继续
            </Button>
          ) : null}
          {isActive ? (
            <Button type="button" size="sm" variant="outline" disabled={busy} onClick={cancel}>
              取消
            </Button>
          ) : null}
          <Button type="button" size="sm" variant="ghost" onClick={() => selectTab("/tasks")}>
            返回列表
          </Button>
        </div>
      }
    >
      {error ? (
        <p className="mb-3 text-[length:var(--text-sm)] text-destructive">{error}</p>
      ) : null}

      <div className="mx-auto grid w-full max-w-5xl gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="flex flex-col gap-4">
          <AgentThinking
            title="思考过程"
            thoughts={thoughts}
            message={statusMessage}
            controlsDisabled={busy}
            onRestart={restart}
          />
          {crawlCounts ? (
            <CrawlerProgress
              label="采集概况"
              value={progressPercent}
              running={crawlRunning}
              counts={crawlCounts}
              showValue={false}
            />
          ) : isActive ? (
            <div className="rounded-[var(--radius-xl)] border border-border/70 bg-card p-4 text-[length:var(--text-sm)] text-muted-foreground shadow-sm">
              {statusMessage || "分析进行中…"}
              {crawlRunning ? " · 正在采集渠道商品" : null}
              {record.steps.find((step) => step.node === "crawl")?.content?.includes("跳过")
                ? " · 未配置渠道 Cookie，已跳过闲鱼/1688"
                : null}
            </div>
          ) : null}
          {replyText ? (
            <div className="rounded-[var(--radius-xl)] border border-border/70 bg-card p-4 shadow-sm">
              <h3 className="mb-2 font-medium text-foreground">分析结论</h3>
              <p className="whitespace-pre-wrap text-[length:var(--text-sm)] text-foreground/90">
                <TypewriterText text={replyText} streaming={!record.reply} />
              </p>
            </div>
          ) : null}
        </div>
        <RunLog lines={logLines} />
      </div>
    </PageScaffold>
  );
}
