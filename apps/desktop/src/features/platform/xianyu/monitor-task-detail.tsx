/**
 * 监控任务详情页 — 参考 Shadcn Admin project-detail-2。
 *
 * @see https://shadcnblocks-admin.vercel.app/project-management/project-detail-2
 */

import { OWNER_ID } from "@desk/platform/constants";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AsyncButton,
  Button,
  ConfirmModal,
  Loading,
  PageScaffold,
  toast,
} from "@desk/ui";
import { ArrowLeft, ChevronRight, Play, Trash2 } from "@desk/ui/icons";
import type { AiAccount, AiProvider } from "@desk/contracts";
import { managePath } from "@desk/platform/compile";
import { aiConfigGet } from "@desk/platform/ipc/ai";
import { accountList, type XianyuAccount } from "@desk/platform/ipc/account";
import { listenMonitorProgress } from "@desk/platform/events";
import {
  monitorGenerateKeywords,
  monitorRunList,
  monitorTaskDelete,
  monitorTaskList,
  monitorTaskPauseSchedule,
  monitorTaskResumeSchedule,
  monitorTaskRun,
  monitorTaskSave,
  type MonitorRun,
  type MonitorTask,
} from "@desk/platform/ipc/xianyu-monitor";
import { useWorkspaceNav } from "../../../app/use-workspace-tabs";
import { BUILT_IN_PROVIDERS } from "@feature/agent/builtin-providers";
import { getErrorMessage } from "@desk/utils";
import { MonitorScheduleBar } from "./monitor/schedule-bar";
import { RunRecordsSection } from "./monitor/run-records";
import { EMPTY_FORM, TaskForm, type AiAccountOption, type MonitorForm } from "./monitor/task-form";
import {
  formatMonitorTime,
  runSuccessRate,
  taskShortCode,
  taskStatusLabel,
} from "./monitor/monitor-utils";

type DetailTab = "overview" | "runs" | "settings";

function toAccountOptions(accounts: XianyuAccount[]) {
  return accounts.map((account) => ({
    id: account.account_id,
    label: account.display_name || account.login_id || account.account_id,
  }));
}

function toAiAccountOptions(accounts: AiAccount[], providers: AiProvider[]): AiAccountOption[] {
  const providerName = new Map(providers.map((provider) => [provider.id, provider.name]));
  const options: AiAccountOption[] = accounts.map((account) => ({
    id: account.id,
    label: `${providerName.get(account.provider_id) ?? "未知平台"} · ${account.name}`,
  }));
  for (const provider of BUILT_IN_PROVIDERS) {
    if (provider.authless) {
      options.push({
        id: `provider:${provider.id}`,
        label: `${provider.name}（本地）`,
      });
    }
  }
  return options;
}

function runStatusCounts(runs: MonitorRun[]) {
  return {
    total: runs.length,
    running: runs.filter((run) => run.status === "running").length,
    success: runs.filter((run) => run.status === "success").length,
    failed: runs.filter((run) => run.status === "failed").length,
  };
}

export interface XianyuMonitorTaskDetailPageProps {
  taskId: string;
}

/** 监控任务详情页。 */
export function XianyuMonitorTaskDetailPage({ taskId }: XianyuMonitorTaskDetailPageProps) {
  const { selectTab } = useWorkspaceNav();
  const [task, setTask] = useState<MonitorTask | null>(null);
  const [runs, setRuns] = useState<MonitorRun[]>([]);
  const [accounts, setAccounts] = useState<XianyuAccount[]>([]);
  const [aiAccountOptions, setAiAccountOptions] = useState<AiAccountOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningTaskId, setRunningTaskId] = useState<string | null>(null);
  const [tab, setTab] = useState<DetailTab>("runs");
  const [form, setForm] = useState<MonitorForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [pausingSchedule, setPausingSchedule] = useState(false);
  const [resumingSchedule, setResumingSchedule] = useState(false);
  const pendingNavTaskId = useRef<string | null>(null);

  const accountOptions = useMemo(() => toAccountOptions(accounts), [accounts]);
  const aiAccountLabelMap = useMemo(
    () => new Map(aiAccountOptions.map((option) => [option.id, option.label])),
    [aiAccountOptions],
  );
  const accountLabel = useMemo(() => {
    if (!task) return "—";
    return accountOptions.find((item) => item.id === task.accountId)?.label ?? task.accountId;
  }, [task, accountOptions]);
  const aiLabel = useMemo(() => {
    if (!task) return "—";
    return aiAccountLabelMap.get(task.aiAccountId) ?? task.aiAccountId;
  }, [task, aiAccountLabelMap]);

  const loadTask = useCallback(async () => {
    const list = await monitorTaskList(OWNER_ID);
    const found = list.find((item) => item.id === taskId) ?? null;
    setTask(found);
    return found;
  }, [taskId]);

  const loadRuns = useCallback(async () => {
    const list = await monitorRunList(OWNER_ID, taskId);
    setRuns(list);
    if (list[0]?.status === "running") {
      setRunningTaskId(taskId);
    } else {
      setRunningTaskId(null);
    }
    return list;
  }, [taskId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void Promise.all([loadTask(), loadRuns(), accountList(OWNER_ID), aiConfigGet()])
      .then(([found, , accountRows, aiConfig]) => {
        if (cancelled) return;
        setAccounts(accountRows);
        setAiAccountOptions(toAiAccountOptions(aiConfig.accounts, aiConfig.providers));
        if (!found) {
          toast.error("监控任务不存在");
          selectTab(managePath("monitor"));
        }
      })
      .catch((error) => {
        if (!cancelled) toast.error(getErrorMessage(error));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadTask, loadRuns, selectTab]);

  useEffect(() => {
    if (!task) return;
    setForm({
      name: task.name,
      intent: task.intent,
      keywords: task.keywords.join("\n"),
      accountId: task.accountId,
      aiAccountId: task.aiAccountId,
      aiFailoverEnabled: task.aiFailoverEnabled ?? true,
      aiAccountOrder: task.aiAccountOrder ?? [],
      intervalMinutes: String(task.intervalMinutes),
      aiCriteria: task.aiCriteria,
      enabled: task.enabled,
    });
  }, [task]);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    void listenMonitorProgress((payload) => {
      if (payload.taskId !== taskId) return;
      if (payload.stage === "started") {
        if (pendingNavTaskId.current === payload.taskId) {
          pendingNavTaskId.current = null;
          setRunningTaskId(null);
          selectTab(`${managePath("monitor")}/runs/${payload.runId}`);
          return;
        }
        setRunningTaskId(payload.taskId);
        void loadRuns();
        void loadTask();
        return;
      }
      if (payload.stage === "finished" || payload.stage === "failed") {
        setRunningTaskId(null);
        void loadRuns();
        void loadTask();
      }
    }).then((fn) => {
      unlisten = fn;
    });
    return () => {
      unlisten?.();
    };
  }, [taskId, loadRuns, loadTask, selectTab]);

  async function handleSave() {
    if (!task) return;
    if (!form.name.trim() || !form.intent.trim() || !form.aiCriteria.trim()) {
      toast.error("请填写任务名称、购买意图和 AI 筛选标准");
      return;
    }
    setSaving(true);
    try {
      const saved = await monitorTaskSave({
        ownerId: OWNER_ID,
        id: task.id,
        name: form.name.trim(),
        intent: form.intent.trim(),
        keywords: form.keywords
          .split(/[\n,]+/)
          .map((item) => item.trim())
          .filter(Boolean),
        accountId: form.accountId,
        aiAccountId: form.aiAccountId,
        aiFailoverEnabled: form.aiFailoverEnabled,
        aiAccountOrder: form.aiAccountOrder,
        intervalMinutes: Number(form.intervalMinutes) || 5,
        enabled: form.enabled,
        aiCriteria: form.aiCriteria.trim(),
      });
      setTask(saved);
      toast.success("监控任务已保存");
      setTab("runs");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerateKeywords() {
    if (!form.intent.trim() || !form.aiCriteria.trim()) {
      toast.error("请先填写购买意图和 AI 筛选标准");
      return;
    }
    setGenerating(true);
    try {
      const keywords = await monitorGenerateKeywords({
        ownerId: OWNER_ID,
        intent: form.intent.trim(),
        aiCriteria: form.aiCriteria.trim(),
        aiAccountId: form.aiAccountId,
        aiFailoverEnabled: form.aiFailoverEnabled,
        aiAccountOrder: form.aiAccountOrder,
      });
      setForm((current) => ({ ...current, keywords: keywords.join("\n") }));
      toast.success(`已生成 ${keywords.length} 个关键词`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setGenerating(false);
    }
  }

  function handleRun() {
    pendingNavTaskId.current = taskId;
    setRunningTaskId(taskId);
    void monitorTaskRun(OWNER_ID, taskId).catch((error) => {
      toast.error(getErrorMessage(error));
      pendingNavTaskId.current = null;
      setRunningTaskId(null);
    });
  }

  async function handlePauseSchedule() {
    setPausingSchedule(true);
    try {
      const updated = await monitorTaskPauseSchedule(OWNER_ID, taskId);
      setTask(updated);
      toast.success("定时已暂停，剩余时间已冻结");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setPausingSchedule(false);
    }
  }

  async function handleResumeSchedule() {
    setResumingSchedule(true);
    try {
      const updated = await monitorTaskResumeSchedule(OWNER_ID, taskId);
      setTask(updated);
      toast.success("定时已恢复");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setResumingSchedule(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await monitorTaskDelete(OWNER_ID, taskId);
      toast.success("任务已删除");
      selectTab(managePath("monitor"));
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setDeleting(false);
      setDeleteOpen(false);
    }
  }

  if (loading) {
    return (
      <PageScaffold>
        <Loading size="lg" text="加载监控详情" className="py-20" />
      </PageScaffold>
    );
  }

  if (!task) {
    return null;
  }

  const { closed, total } = runSuccessRate(runs);
  const statusCounts = runStatusCounts(runs);
  const successRate = total > 0 ? Math.round((closed / total) * 100) : 0;

  const tabs: { id: DetailTab; label: string }[] = [
    { id: "runs", label: "运行记录" },
    { id: "settings", label: "配置" },
  ];

  return (
    <PageScaffold scroll>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-2 text-[length:var(--text-xs)] text-muted-foreground">
          <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => selectTab(managePath("monitor"))}>
            <ArrowLeft className="mr-1 size-3.5" aria-hidden />
            商品监控
          </Button>
          <ChevronRight className="size-3" aria-hidden />
          <span className="text-foreground">{task.name}</span>
        </div>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-3">
            <h1 className="text-[length:var(--text-2xl)] font-semibold tracking-tight text-foreground">
              {task.name}
            </h1>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-[length:var(--text-xs)]">
                定时监控
              </span>
              <span className="rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-[length:var(--text-xs)]">
                {taskStatusLabel(task)}
              </span>
              <span className="rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-[length:var(--text-xs)]">
                {accountLabel}
              </span>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[length:var(--text-xs)] text-muted-foreground">
              <span>
                编号 <span className="font-mono text-foreground">{taskShortCode(task.id)}</span>
              </span>
              <span>
                间隔 <span className="text-foreground">{task.intervalMinutes} 分钟</span>
              </span>
              <span>
                更新 <span className="text-foreground">{formatMonitorTime(task.updatedAt)}</span>
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <AsyncButton onClick={handleRun} disabled={runningTaskId === taskId}>
              <Play className="mr-1.5 size-4" aria-hidden />
              立即运行
            </AsyncButton>
            <Button variant="outline" onClick={() => setDeleteOpen(true)}>
              <Trash2 className="mr-1.5 size-4" aria-hidden />
              删除
            </Button>
          </div>
        </div>

        <MonitorScheduleBar
          task={task}
          pausing={pausingSchedule}
          resuming={resumingSchedule}
          onPause={() => void handlePauseSchedule()}
          onResume={() => void handleResumeSchedule()}
        />

        <div className="grid gap-3 sm:grid-cols-3">
          {[
            { label: "监控周期", value: `${task.intervalMinutes} 分钟`, hint: task.enabled ? "已启用" : "已停用" },
            { label: "运行完成", value: total > 0 ? `${closed} / ${total}` : "—", hint: `${successRate}% 成功率` },
            { label: "关键词", value: String(task.keywords.length), hint: "搜索词数量" },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-[var(--radius-xl)] border border-border/80 bg-card/80 p-4 backdrop-blur-sm"
            >
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{item.label}</p>
              <p className="mt-1 text-[length:var(--text-2xl)] font-semibold tabular-nums">{item.value}</p>
              <p className="mt-1 text-[length:var(--text-xs)] text-muted-foreground">{item.hint}</p>
            </div>
          ))}
        </div>

        {task.lastError ? (
          <div className="rounded-[var(--radius-lg)] border border-destructive/30 bg-destructive/5 px-4 py-3 text-[length:var(--text-sm)]">
            <span className="font-medium text-destructive">上次运行失败：</span>
            <span className="text-muted-foreground"> {task.lastError}</span>
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-4">
          {[
            { label: "总运行", value: statusCounts.total },
            { label: "进行中", value: statusCounts.running },
            { label: "成功", value: statusCounts.success },
            { label: "失败", value: statusCounts.failed },
          ].map((item) => (
            <div key={item.label} className="rounded-[var(--radius-lg)] border border-border/70 bg-card/60 p-3">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{item.label}</p>
              <p className="mt-0.5 text-[length:var(--text-xl)] font-semibold tabular-nums">{item.value}</p>
            </div>
          ))}
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-1 rounded-[var(--radius-lg)] border border-border/80 bg-muted/20 p-1">
              {tabs.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`rounded-md px-3 py-1.5 text-[length:var(--text-sm)] transition-colors ${
                    tab === item.id
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                  onClick={() => setTab(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {tab === "overview" ? (
              <div className="space-y-3 rounded-[var(--radius-xl)] border border-border/80 bg-card/80 p-5">
                <h2 className="text-[length:var(--text-sm)] font-medium">购买意图</h2>
                <p className="text-[length:var(--text-sm)] leading-relaxed text-muted-foreground">{task.intent}</p>
              </div>
            ) : null}

            {tab === "runs" ? (
              <div className="rounded-[var(--radius-xl)] border border-border/80 bg-card/80 p-5">
                <RunRecordsSection
                  runs={runs}
                  runningTaskId={runningTaskId}
                  onOpen={(runId) => selectTab(`${managePath("monitor")}/runs/${runId}`)}
                />
              </div>
            ) : null}

            {tab === "settings" ? (
              <TaskForm
                form={form}
                editingExisting
                accountOptions={accountOptions}
                aiAccountOptions={aiAccountOptions}
                aiAccountLabelMap={aiAccountLabelMap}
                saving={saving}
                generating={generating}
                setForm={setForm}
                onSave={() => void handleSave()}
                onGenerateKeywords={() => void handleGenerateKeywords()}
                onCancel={() => setTab("runs")}
              />
            ) : null}
          </div>

          <aside className="space-y-4">
            <section className="rounded-[var(--radius-xl)] border border-border/80 bg-card/80 p-4">
              <h2 className="text-[length:var(--text-sm)] font-medium">关键词</h2>
              <p className="mt-1 text-[length:var(--text-xs)] text-muted-foreground">
                共 {task.keywords.length} 个
              </p>
              <ul className="mt-3 space-y-1.5">
                {(task.keywords.length > 0 ? task.keywords : ["（运行时 AI 生成）"]).map((keyword) => (
                  <li
                    key={keyword}
                    className="flex items-center justify-between rounded-md border border-border/60 px-2 py-1.5 text-[length:var(--text-xs)]"
                  >
                    <span className="truncate">{keyword}</span>
                    <ChevronRight className="size-3 shrink-0 text-muted-foreground" aria-hidden />
                  </li>
                ))}
              </ul>
            </section>

            <section className="rounded-[var(--radius-xl)] border border-border/80 bg-card/80 p-4">
              <h2 className="text-[length:var(--text-sm)] font-medium">执行账号</h2>
              <ul className="mt-3 space-y-2 text-[length:var(--text-xs)]">
                <li>
                  <span className="text-muted-foreground">闲鱼 </span>
                  <span className="text-foreground">{accountLabel}</span>
                </li>
                <li>
                  <span className="text-muted-foreground">AI </span>
                  <span className="text-foreground">{aiLabel}</span>
                </li>
              </ul>
            </section>

            <section className="rounded-[var(--radius-xl)] border border-border/80 bg-card/80 p-4">
              <h2 className="text-[length:var(--text-sm)] font-medium">时间</h2>
              <dl className="mt-3 space-y-2 text-[length:var(--text-xs)]">
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">创建</dt>
                  <dd>{formatMonitorTime(task.createdAt)}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">上次运行</dt>
                  <dd>{formatMonitorTime(task.lastRunAt)}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">最近更新</dt>
                  <dd>{formatMonitorTime(task.updatedAt)}</dd>
                </div>
              </dl>
            </section>

            <section className="rounded-[var(--radius-xl)] border border-border/80 bg-card/80 p-4">
              <h2 className="text-[length:var(--text-sm)] font-medium">筛选标准</h2>
              <p className="mt-2 text-[length:var(--text-xs)] leading-relaxed text-muted-foreground">
                {task.aiCriteria || "—"}
              </p>
            </section>
          </aside>
        </div>
      </div>

      <ConfirmModal
        isOpen={deleteOpen}
        title="删除监控任务"
        message={`确定删除「${task.name}」吗？`}
        confirmText="删除"
        type="danger"
        loading={deleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => setDeleteOpen(false)}
      />
    </PageScaffold>
  );
}
