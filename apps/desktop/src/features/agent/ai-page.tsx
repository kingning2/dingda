/**
 * AI 配置独立页面 — 按平台分组，组内管理账号。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */

import { useEffect, useState } from "react";
import {
  Button,
  ConfirmModal,
  Input,
  Loading,
  PageCardGrid,
  PageGlowCard,
  PageScaffold,
} from "@desk/ui";
import { Plus } from "@desk/ui/icons";
import type { AiAccount } from "@desk/contracts";
import { ACCOUNT_PROVIDERS, BUILT_IN_PROVIDERS, type BuiltInProvider } from "./builtin-providers";
import { AiAccountCard } from "./ai-account-card";
import { AiAccountDialog } from "./ai-account-dialog";
import { AI_GRAPH_NODES, useAiConfigStore } from "./use-ai-config";

function toError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * AI 配置页。
 *
 * @author Xiaoman
 * @created 2026-08-20
 *
 * @returns 页面节点
 */
export function AiPage() {
  const providers = useAiConfigStore((state) => state.providers);
  const accounts = useAiConfigStore((state) => state.accounts);
  const loading = useAiConfigStore((state) => state.loading);
  const loaded = useAiConfigStore((state) => state.loaded);
  const loadError = useAiConfigStore((state) => state.error);
  const load = useAiConfigStore((state) => state.load);
  const removeAccount = useAiConfigStore((state) => state.removeAccount);
  const setProviderDefaultModel = useAiConfigStore((state) => state.setProviderDefaultModel);

  const ollama = providers.find((provider) => provider.id === "ollama");

  const [dialogSeq, setDialogSeq] = useState(0);
  const [accountDialog, setAccountDialog] = useState<{
    providerId: string;
    account: AiAccount | null;
  } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<AiAccount | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [ollamaModel, setOllamaModel] = useState(ollama?.default_model ?? "");
  const [ollamaError, setOllamaError] = useState<string | null>(null);

  useEffect(() => {
    if (!loaded && !loading) {
      void load();
    }
  }, [loaded, loading, load]);

  useEffect(() => {
    setOllamaModel(ollama?.default_model ?? "");
  }, [ollama?.default_model]);

  function openAccountDialog(providerId: string, account: AiAccount | null) {
    setDialogSeq((seq) => seq + 1);
    setAccountDialog({ providerId, account });
  }

  async function saveOllamaModel() {
    if (!ollama) {
      return;
    }
    const trimmed = ollamaModel.trim();
    if (trimmed === (ollama.default_model ?? "")) {
      return;
    }
    setOllamaError(null);
    try {
      await setProviderDefaultModel(ollama.id, trimmed);
    } catch (error) {
      setOllamaError(toError(error));
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }
    setDeleting(true);
    try {
      await removeAccount(pendingDelete.id);
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <PageScaffold
      title="AI 配置"
      subtitle="管理客服自动回复与双方比价使用的 AI 账号，密钥仅保存在本机"
    >
      {loadError ? (
        <p className="mb-4 text-[length:var(--text-sm)] text-red-600 dark:text-red-400">
          {loadError}
        </p>
      ) : null}

      {loading && !loaded ? <Loading size="sm" text="加载 AI 配置" /> : null}

      <div className="flex flex-col gap-8">
        {ACCOUNT_PROVIDERS.map((catalog) => {
          const provider = providers.find((item) => item.id === catalog.id) ?? catalog;
          const providerAccounts = accounts.filter(
            (account) => account.provider_id === catalog.id,
          );
          return (
            <section key={catalog.id} className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2.5">
                  <img src={catalog.logo} alt="" aria-hidden className="h-6 w-auto shrink-0" />
                  <div className="min-w-0">
                    <h2 className="font-medium text-foreground">{catalog.name}</h2>
                    <p className="text-[length:var(--text-xs)] text-muted-foreground">
                      {catalog.hint}
                    </p>
                  </div>
                </div>
                <Button size="sm" onClick={() => openAccountDialog(catalog.id, null)}>
                  <Plus className="size-3.5" aria-hidden />
                  添加账号
                </Button>
              </div>

              {providerAccounts.length > 0 ? (
                <PageCardGrid>
                  {providerAccounts.map((account) => (
                    <AiAccountCard
                      key={account.id}
                      account={account}
                      provider={provider}
                      onEdit={() => openAccountDialog(provider.id, account)}
                      onDelete={() => setPendingDelete(account)}
                    />
                  ))}
                </PageCardGrid>
              ) : (
                <p className="rounded-[var(--radius-md)] border border-dashed border-border/80 px-3 py-6 text-center text-[length:var(--text-sm)] text-muted-foreground">
                  还没有 {catalog.name} 账号
                </p>
              )}
            </section>
          );
        })}

        {ollama ? (
          <LocalAiSection
            provider={ollama}
            model={ollamaModel}
            error={ollamaError}
            onModelChange={setOllamaModel}
            onSave={() => void saveOllamaModel()}
          />
        ) : null}

        <GraphModelsSection />
      </div>

      <AiAccountDialog
        key={`account-${dialogSeq}`}
        open={accountDialog !== null}
        provider={
          providers.find((item) => item.id === accountDialog?.providerId) ??
          BUILT_IN_PROVIDERS.find((item) => item.id === accountDialog?.providerId) ??
          null
        }
        account={accountDialog?.account ?? null}
        onClose={() => setAccountDialog(null)}
      />

      <ConfirmModal
        isOpen={pendingDelete !== null}
        title="删除账号"
        message="确定删除该 AI 账号吗？"
        confirmText="删除"
        type="danger"
        loading={deleting}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPendingDelete(null)}
      />
    </PageScaffold>
  );
}

/**
 * 本地 AI 配置区块。
 */
function LocalAiSection({
  provider,
  model,
  error,
  onModelChange,
  onSave,
}: {
  provider: BuiltInProvider;
  model: string;
  error: string | null;
  onModelChange: (value: string) => void;
  onSave: () => void;
}) {
  return (
    <section className="space-y-3">
      <div className="flex min-w-0 items-center gap-2.5">
        <img
          src={provider.logo}
          alt=""
          aria-hidden
          className="h-6 w-auto shrink-0 dark:invert"
        />
        <div>
          <h2 className="font-medium text-foreground">{provider.name}</h2>
          <p className="text-[length:var(--text-xs)] text-muted-foreground">{provider.hint}</p>
        </div>
      </div>
      <PageGlowCard className="max-w-md border border-border/70 bg-card p-4 shadow-sm">
        <div className="flex flex-col gap-2">
          <label
            htmlFor="local-ai-default-model"
            className="text-[length:var(--text-sm)] font-medium text-foreground"
          >
            常用模型
          </label>
          <Input
            id="local-ai-default-model"
            value={model}
            onChange={(event) => onModelChange(event.target.value)}
            onBlur={onSave}
            placeholder={provider.modelPlaceholder}
          />
          {error ? (
            <p className="text-[length:var(--text-sm)] text-red-600 dark:text-red-400">{error}</p>
          ) : null}
        </div>
      </PageGlowCard>
    </section>
  );
}

const NODE_LABELS: Record<string, string> = {
  web_research: "网页调研",
  article_analyze: "文章分析",
  planner: "规划",
  analyze: "核验分析",
  finalize: "成文",
};

/**
 * 比价图节点模型路由与欠费 failover。
 */
function GraphModelsSection() {
  const accounts = useAiConfigStore((state) => state.accounts);
  const graphModels = useAiConfigStore((state) => state.graphModels);
  const setGraphNodeAccount = useAiConfigStore((state) => state.setGraphNodeAccount);
  const setFailoverEnabled = useAiConfigStore((state) => state.setFailoverEnabled);
  const setFailoverAccountIds = useAiConfigStore((state) => state.setFailoverAccountIds);

  return (
    <section className="space-y-3">
      <div>
        <h2 className="font-medium text-foreground">比价图模型路由</h2>
        <p className="text-[length:var(--text-xs)] text-muted-foreground">
          为需要 AI 的节点指定账号；欠费时按 failover 顺序换模重试
        </p>
      </div>
      <PageGlowCard className="space-y-4 border border-border/70 bg-card p-4 shadow-sm">
        {AI_GRAPH_NODES.map((node) => {
          const current =
            graphModels.node_accounts?.find((row) => row.node === node)?.account_id ?? "";
          return (
            <div key={node} className="flex flex-wrap items-center gap-3">
              <label className="w-28 text-[length:var(--text-sm)] font-medium text-foreground">
                {NODE_LABELS[node] ?? node}
              </label>
              <select
                className="min-w-[12rem] rounded-[var(--radius-md)] border border-border bg-background px-2 py-1.5 text-[length:var(--text-sm)]"
                value={current}
                onChange={(event) => void setGraphNodeAccount(node, event.target.value)}
              >
                <option value="">（默认首个账号）</option>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name}
                  </option>
                ))}
              </select>
            </div>
          );
        })}
        <label className="flex items-center gap-2 text-[length:var(--text-sm)]">
          <input
            type="checkbox"
            checked={graphModels.failover_enabled !== false}
            onChange={(event) => void setFailoverEnabled(event.target.checked)}
          />
          欠费自动换模
        </label>
        <div className="flex flex-col gap-2">
          <span className="text-[length:var(--text-sm)] font-medium text-foreground">
            Failover 顺序（逗号分隔账号 id）
          </span>
          <Input
            value={(graphModels.failover_account_ids ?? []).join(",")}
            onChange={(event) => {
              const ids = event.target.value
                .split(",")
                .map((part) => part.trim())
                .filter(Boolean);
              void setFailoverAccountIds(ids);
            }}
            placeholder={accounts.map((a) => a.id).join(",") || "acc-1,acc-2"}
          />
        </div>
      </PageGlowCard>
    </section>
  );
}
