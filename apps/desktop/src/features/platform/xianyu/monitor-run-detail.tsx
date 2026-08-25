/**
 * 闲鱼监控运行详情页 — agent 式转录（左：流式步骤 / 右：商品）。
 * 步骤仅通过 Rust 事件增量追加，运行中不整页 refetch。
 */

import { OWNER_ID } from "@desk/platform/constants";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Loading, PageScaffold, ScrollArea, motion, toast } from "@desk/ui";
import { ArrowLeft, ExternalLink, Play } from "@desk/ui/icons";
import { managePath } from "@desk/platform/compile";
import {
  monitorResultList,
  monitorRunGet,
  monitorTaskList,
  monitorTaskRun,
  type MonitorResult,
  type MonitorRun,
} from "@desk/platform/ipc/xianyu-monitor";
import { listenMonitorMatch, listenMonitorProgress } from "@desk/platform/events";
import { useWorkspaceNav } from "../../../app/use-workspace-tabs";
import { formatRunTime, ThinkingDots, TranscriptStep } from "./monitor-console";
import { monitorStepKey, patchMonitorRunFromProgress } from "./monitor/run-stream";

const RESULT_SPRING = { type: "spring", stiffness: 360, damping: 30 } as const;
const STICK_THRESHOLD_PX = 96;

export interface XianyuMonitorRunDetailPageProps {
  runId: string;
}

function ResultCard({ item }: { item: MonitorResult }) {
  return (
    <motion.li initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={RESULT_SPRING}>
      <article
        className={`flex gap-3 rounded-xl border p-3 ${
          item.aiRecommended ? "border-primary/40 bg-primary/5" : "border-border bg-card"
        }`}
      >
        {item.image ? (
          <img
            src={item.image}
            alt={item.title}
            loading="lazy"
            className="h-20 w-20 shrink-0 rounded-lg border border-border object-cover"
            onError={(event) => {
              event.currentTarget.style.display = "none";
            }}
          />
        ) : null}
        <div className="min-w-0 flex-1 space-y-1">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="line-clamp-2 break-words text-sm font-medium hover:underline"
          >
            {item.title}
          </a>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">{item.priceText || "—"}</span>
            {item.sellerName ? <span className="break-all">{item.sellerName}</span> : null}
            {item.location ? <span>{item.location}</span> : null}
          </div>
          <p className="break-words text-xs leading-relaxed text-muted-foreground">{item.aiReason}</p>
        </div>
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="shrink-0 text-muted-foreground hover:text-foreground"
        >
          <ExternalLink className="size-4" />
        </a>
      </article>
    </motion.li>
  );
}

/** 闲鱼监控运行详情页。 */
export function XianyuMonitorRunDetailPage({ runId }: XianyuMonitorRunDetailPageProps) {
  const { selectTab } = useWorkspaceNav();
  const [run, setRun] = useState<MonitorRun | null>(null);
  const [results, setResults] = useState<MonitorResult[]>([]);
  const [taskName, setTaskName] = useState("");
  const [loading, setLoading] = useState(true);
  const transcriptViewportRef = useRef<HTMLDivElement>(null);
  const resultsViewportRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const taskIdRef = useRef<string | null>(null);
  const stepCountRef = useRef(0);

  const scrollTranscriptToBottom = useCallback((force = false) => {
    const el = transcriptViewportRef.current;
    if (!el || (!force && !stickToBottomRef.current)) return;
    el.scrollTop = el.scrollHeight;
  }, []);

  useEffect(() => {
    const el = transcriptViewportRef.current;
    if (!el) return;
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickToBottomRef.current = distance <= STICK_THRESHOLD_PX;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [loading, run?.id]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setRun(null);
    setResults([]);
    taskIdRef.current = null;
    stepCountRef.current = 0;
    stickToBottomRef.current = true;

    void (async () => {
      try {
        const found = await monitorRunGet(OWNER_ID, runId);
        if (cancelled) return;
        if (!found) {
          toast.error("运行记录不存在");
          selectTab(managePath("monitor"));
          return;
        }
        setRun(found);
        stepCountRef.current = found.steps.length;
        taskIdRef.current = found.taskId;
        const tasks = await monitorTaskList(OWNER_ID);
        if (cancelled) return;
        setTaskName(
          tasks.find((task) => task.id === found.taskId)?.name ??
            found.steps[0]?.taskName ??
            "监控任务",
        );
        void monitorResultList(OWNER_ID, found.taskId)
          .then((list) => {
            if (!cancelled) setResults(list);
          })
          .catch((error) => {
            if (!cancelled) {
              toast.error(error instanceof Error ? error.message : String(error));
            }
          });
      } catch (error) {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : String(error));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [runId, selectTab]);

  useEffect(() => {
    let unlistenProgress: (() => void) | undefined;
    let unlistenMatch: (() => void) | undefined;

    void listenMonitorProgress((payload) => {
      if (payload.runId === runId) {
        setRun((prev) => {
          if (!prev) return prev;
          return patchMonitorRunFromProgress(prev, payload);
        });
        if (payload.stage === "matched" || payload.stage === "finished") {
          const taskId = taskIdRef.current;
          if (taskId) {
            void monitorResultList(OWNER_ID, taskId)
              .then(setResults)
              .catch(() => undefined);
          }
        }
        return;
      }
      const taskId = taskIdRef.current;
      if (taskId && payload.taskId === taskId && payload.stage === "started") {
        selectTab(`${managePath("monitor")}/runs/${payload.runId}`);
      }
    }).then((fn) => {
      unlistenProgress = fn;
    });

    void listenMonitorMatch((payload) => {
      const taskId = taskIdRef.current;
      if (!taskId || payload.taskId !== taskId) return;
      void monitorResultList(OWNER_ID, taskId)
        .then(setResults)
        .catch(() => undefined);
    }).then((fn) => {
      unlistenMatch = fn;
    });

    return () => {
      unlistenProgress?.();
      unlistenMatch?.();
    };
  }, [runId, selectTab]);

  useEffect(() => {
    const count = run?.steps.length ?? 0;
    if (count > stepCountRef.current) {
      stepCountRef.current = count;
      requestAnimationFrame(() => scrollTranscriptToBottom());
    }
  }, [run?.steps.length, scrollTranscriptToBottom]);

  const running = run?.status === "running";

  function handleRerun() {
    if (!run) return;
    void monitorTaskRun(OWNER_ID, run.taskId).catch((error) =>
      toast.error(error instanceof Error ? error.message : String(error)),
    );
  }

  function handleBack() {
    const taskId = taskIdRef.current;
    if (taskId) {
      selectTab(`${managePath("monitor")}/tasks/${encodeURIComponent(taskId)}`);
      return;
    }
    selectTab(managePath("monitor"));
  }

  return (
    <PageScaffold scroll={false} fill containerPadding="md" className="min-h-0">
      {loading ? (
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <Loading />
        </div>
      ) : run ? (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[var(--radius-lg)] border border-border bg-card">
          <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border/60 px-4 py-3 md:px-5">
            <div className="flex min-w-0 items-center gap-2">
              <Button variant="ghost" size="sm" onClick={handleBack}>
                <ArrowLeft className="size-4" />
              </Button>
              <div className="min-w-0">
                <h2 className="truncate text-sm font-semibold">{taskName || "运行详情"}</h2>
                <p className="text-xs text-muted-foreground">
                  {run.status === "running" ? "运行中" : run.status === "success" ? "成功" : "失败"} ·{" "}
                  {formatRunTime(run.startedAt)}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button size="sm" onClick={handleRerun} disabled={running}>
                <Play className="mr-1.5 size-4" />
                立即运行
              </Button>
            </div>
          </header>

          <div className="flex min-h-0 flex-1 overflow-hidden">
            <section className="flex min-h-0 min-w-0 flex-1 flex-col border-r border-border/60 bg-background">
              <div className="flex shrink-0 items-center justify-between border-b border-border/60 px-4 py-2.5 md:px-5">
                <span className="text-xs font-medium">运行过程</span>
                <span className="text-[10px] text-muted-foreground">{run.steps.length} 条</span>
              </div>
              <ScrollArea className="min-h-0 flex-1" viewportRef={transcriptViewportRef}>
                <div className="space-y-3 px-4 py-3 md:px-5 md:py-4">
                  {run.steps.map((step, index) => (
                    <TranscriptStep key={monitorStepKey(step, index)} step={step} />
                  ))}
                  {running ? <ThinkingDots /> : null}
                </div>
              </ScrollArea>
            </section>

            <section className="flex min-h-0 min-w-0 flex-1 flex-col bg-muted/10">
              <div className="flex shrink-0 items-center justify-between border-b border-border/60 px-4 py-2.5 md:px-5">
                <span className="text-xs font-medium">商品（{results.length}）</span>
              </div>
              <ScrollArea className="min-h-0 flex-1" viewportRef={resultsViewportRef}>
                <div className="px-4 py-3 md:px-5 md:py-4">
                  {results.length === 0 ? (
                    <p className="text-sm text-muted-foreground">暂无商品结果。</p>
                  ) : (
                    <ul className="space-y-3 pb-1">
                      {results.map((item) => (
                        <ResultCard key={item.id} item={item} />
                      ))}
                    </ul>
                  )}
                </div>
              </ScrollArea>
            </section>
          </div>
        </div>
      ) : null}
    </PageScaffold>
  );
}
