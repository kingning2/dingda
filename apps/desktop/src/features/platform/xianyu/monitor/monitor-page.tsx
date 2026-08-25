/**
 * 闲鱼商品监控列表 — 流程卡片网格（project-list-1），点击进入详情页。
 *
 * @see https://shadcnblocks-admin.vercel.app/project-management/project-list-1
 */

import { OWNER_ID } from "@desk/platform/constants";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Loading, PageScaffold, toast } from "@desk/ui";
import type { AiAccount, AiProvider } from "@desk/contracts";
import { aiConfigGet } from "@desk/platform/ipc/ai";
import { accountList, type XianyuAccount } from "@desk/platform/ipc/account";
import { listenMonitorProgress } from "@desk/platform/events";
import {
  monitorGenerateKeywords,
  monitorStats,
  monitorTaskList,
  monitorTaskRun,
  monitorTaskSave,
  type MonitorStats,
  type MonitorTask,
} from "@desk/platform/ipc/xianyu-monitor";
import { useWorkspaceNav } from "../../../../app/use-workspace-tabs";
import { BUILT_IN_PROVIDERS } from "@feature/agent/builtin-providers";
import { getErrorMessage } from "@desk/utils";
import { StatsSection } from "./stats";
import { MonitorToolbar } from "./monitor-toolbar";
import { TaskFlowCard } from "./task-flow-card";
import { EMPTY_FORM, TaskForm, type AiAccountOption, type MonitorForm } from "./task-form";
import {
  filterMonitorTasks,
  monitorTaskDetailPath,
  searchMonitorTasks,
  type MonitorFilter,
} from "./monitor-utils";

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

/** 闲鱼商品监控列表页。 */
export function XianyuMonitorPage() {
  const { selectTab } = useWorkspaceNav();
  const [accounts, setAccounts] = useState<XianyuAccount[]>([]);
  const [aiAccountOptions, setAiAccountOptions] = useState<AiAccountOption[]>([]);
  const [tasks, setTasks] = useState<MonitorTask[]>([]);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [form, setForm] = useState<MonitorForm>(EMPTY_FORM);
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filter, setFilter] = useState<MonitorFilter>("all");

  const accountOptions = useMemo(() => toAccountOptions(accounts), [accounts]);
  const aiAccountLabelMap = useMemo(
    () => new Map(aiAccountOptions.map((option) => [option.id, option.label])),
    [aiAccountOptions],
  );
  const visibleTasks = useMemo(
    () => searchMonitorTasks(filterMonitorTasks(tasks, filter), searchQuery),
    [tasks, filter, searchQuery],
  );

  const loadTasks = useCallback(async () => {
    const list = await monitorTaskList(OWNER_ID);
    setTasks(list);
    return list;
  }, []);

  const loadStats = useCallback(async () => {
    const value = await monitorStats(OWNER_ID);
    setStats(value);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void aiConfigGet()
      .then((config) => {
        if (cancelled) return;
        const options = toAiAccountOptions(config.accounts, config.providers);
        setAiAccountOptions(options);
        if (options.length > 0) {
          setForm((current) => ({
            ...current,
            aiAccountId: current.aiAccountId || options[0]!.id,
          }));
        }
      })
      .catch((error) => {
        if (!cancelled) toast.error(getErrorMessage(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void accountList(OWNER_ID)
      .then((list) => {
        if (cancelled) return;
        const xianyuAccounts = list.filter(
          (item) => (item.platform ?? "xianyu") === "xianyu" && item.status === "active",
        );
        setAccounts(xianyuAccounts);
        if (xianyuAccounts.length > 0) {
          setForm((current) => ({
            ...current,
            accountId: current.accountId || xianyuAccounts[0]!.account_id,
          }));
        }
      })
      .catch((error) => {
        if (!cancelled) toast.error(getErrorMessage(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setLoading(true);
    void loadTasks()
      .catch((error) => toast.error(getErrorMessage(error)))
      .finally(() => setLoading(false));
  }, [loadTasks]);

  useEffect(() => {
    void loadStats().catch((error) => toast.error(getErrorMessage(error)));
  }, [loadStats]);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    void listenMonitorProgress((payload) => {
      if (payload.stage === "finished" || payload.stage === "failed" || payload.stage === "started") {
        void loadTasks();
        void loadStats();
      }
    }).then((fn) => {
      unlisten = fn;
    });
    return () => {
      unlisten?.();
    };
  }, [loadTasks, loadStats]);

  function startCreate() {
    setCreating(true);
    setForm({
      ...EMPTY_FORM,
      accountId: accountOptions[0]?.id ?? "",
      aiAccountId: aiAccountOptions[0]?.id ?? "",
    });
  }

  async function handleSave() {
    if (!form.name.trim() || !form.intent.trim() || !form.aiCriteria.trim()) {
      toast.error("请填写任务名称、购买意图和 AI 筛选标准");
      return;
    }
    if (!form.accountId) {
      toast.error("请选择闲鱼账号");
      return;
    }
    if (!form.aiAccountId) {
      toast.error("请选择 AI 账号");
      return;
    }
    setSaving(true);
    try {
      const saved = await monitorTaskSave({
        ownerId: OWNER_ID,
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
      toast.success("监控任务已保存");
      setCreating(false);
      selectTab(monitorTaskDetailPath(saved.id));
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
    if (!form.aiAccountId) {
      toast.error("请先选择 AI 账号");
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

  function handleRun(taskId: string) {
    void monitorTaskRun(OWNER_ID, taskId)
      .then(() => {
        void loadTasks();
      })
      .catch((error) => toast.error(getErrorMessage(error)));
  }

  return (
    <PageScaffold
      title="商品监控"
      subtitle="定时扫描闲鱼商品，AI 筛选后入库推荐"
    >
      {stats ? <StatsSection stats={stats} /> : null}

      <MonitorToolbar
        taskCount={visibleTasks.length}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        filter={filter}
        onFilterChange={setFilter}
        onCreate={startCreate}
      />

      {loading ? (
        <div className="flex justify-center py-16">
          <Loading text="加载监控任务" />
        </div>
      ) : visibleTasks.length === 0 ? (
        <div className="rounded-[var(--radius-xl)] border border-dashed border-border/80 px-6 py-16 text-center">
          <p className="text-[length:var(--text-sm)] text-muted-foreground">
            {searchQuery.trim() || filter !== "all" ? "没有匹配的任务" : "还没有监控任务"}
          </p>
          {!searchQuery.trim() && filter === "all" ? (
            <button
              type="button"
              className="mt-3 text-[length:var(--text-sm)] font-medium text-primary hover:underline"
              onClick={startCreate}
            >
              创建第一个监控流程
            </button>
          ) : null}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visibleTasks.map((task) => (
            <TaskFlowCard
              key={task.id}
              task={task}
              onSelect={() => selectTab(monitorTaskDetailPath(task.id))}
              onRun={() => handleRun(task.id)}
            />
          ))}
        </div>
      )}

      {creating ? (
        <TaskForm
          form={form}
          editingExisting={false}
          accountOptions={accountOptions}
          aiAccountOptions={aiAccountOptions}
          aiAccountLabelMap={aiAccountLabelMap}
          saving={saving}
          generating={generating}
          setForm={setForm}
          onSave={() => void handleSave()}
          onGenerateKeywords={() => void handleGenerateKeywords()}
          onCancel={() => setCreating(false)}
        />
      ) : null}
    </PageScaffold>
  );
}
