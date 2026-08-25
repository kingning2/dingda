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
import { useAiConfigStore } from "./use-ai-config";

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
      subtitle="管理客服自动回复与商品监控使用的 AI 账号，密钥仅保存在本机"
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
