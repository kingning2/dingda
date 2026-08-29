/**
 * AI 模型设置页 — 单添加按钮 + 账号卡片平铺；平台目录由后端返回。
 */

import { useEffect, useState } from "react";
import {
  Button,
  ConfirmModal,
  Input,
  Label,
  Loading,
  PageCardGrid,
  PageGlowCard,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
} from "@desk/ui";
import { Plus } from "@desk/ui/icons";
import type { AiAccount } from "@desk/contracts";
import { SettingsLayoutPage } from "../../settings-layout";
import { AiAccountCard } from "./ai-account-card";
import { AiAccountDialog } from "./ai-account-dialog";
import { AI_GRAPH_NODES, useAiConfigStore } from "./use-ai-config";

/** AI 模型设置（统一设置壳，无页面大标题）。 */
export function SettingsAiPage() {
  const accounts = useAiConfigStore((state) => state.accounts);
  const catalog = useAiConfigStore((state) => state.catalog);
  const loading = useAiConfigStore((state) => state.loading);
  const loaded = useAiConfigStore((state) => state.loaded);
  const loadError = useAiConfigStore((state) => state.error);
  const load = useAiConfigStore((state) => state.load);
  const removeAccount = useAiConfigStore((state) => state.removeAccount);
  const resolveProvider = useAiConfigStore((state) => state.resolveProvider);

  const [dialogSeq, setDialogSeq] = useState(0);
  const [accountDialog, setAccountDialog] = useState<AiAccount | null | "new">(null);
  const [pendingDelete, setPendingDelete] = useState<AiAccount | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!loaded && !loading) {
      void load();
    }
  }, [loaded, loading, load]);

  function openCreate() {
    setDialogSeq((seq) => seq + 1);
    setAccountDialog("new");
  }

  function openEdit(account: AiAccount) {
    setDialogSeq((seq) => seq + 1);
    setAccountDialog(account);
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
    <SettingsLayoutPage>
      {loadError ? (
        <p className="mb-4 text-[length:var(--text-sm)] text-red-600 dark:text-red-400">
          {loadError}
        </p>
      ) : null}

      {loading && !loaded ? <Loading size="sm" text="加载 AI 配置" /> : null}

      <div className="flex flex-col gap-8">
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[length:var(--text-sm)] text-muted-foreground">
              添加 LangGraph 可用的 AI 账号，密钥仅保存在本机
            </p>
            <Button size="sm" onClick={openCreate} disabled={catalog.length === 0}>
              <Plus className="size-3.5" aria-hidden />
              添加账号
            </Button>
          </div>

          {accounts.length > 0 ? (
            <PageCardGrid>
              {accounts.map((account) => (
                <AiAccountCard
                  key={account.id}
                  account={account}
                  provider={resolveProvider(account.provider_id)}
                  onEdit={() => openEdit(account)}
                  onDelete={() => setPendingDelete(account)}
                />
              ))}
            </PageCardGrid>
          ) : loaded ? (
            <p className="rounded-[var(--radius-md)] border border-dashed border-border/80 px-3 py-6 text-center text-[length:var(--text-sm)] text-muted-foreground">
              还没有 AI 账号，点击上方添加
            </p>
          ) : null}
        </section>

        <GraphModelsSection />
      </div>

      <AiAccountDialog
        key={`account-${dialogSeq}`}
        open={accountDialog !== null}
        catalog={catalog}
        account={accountDialog === "new" ? null : accountDialog}
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
    </SettingsLayoutPage>
  );
}

const NODE_LABELS: Record<string, string> = {
  web_research: "网页调研",
  article_analyze: "文章分析",
  planner: "规划",
  analyze: "核验分析",
  finalize: "成文",
};

const DEFAULT_ACCOUNT_VALUE = "__default__";

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
              <Label className="w-28 font-medium text-foreground">
                {NODE_LABELS[node] ?? node}
              </Label>
              <Select
                value={current || DEFAULT_ACCOUNT_VALUE}
                onValueChange={(value) =>
                  void setGraphNodeAccount(
                    node,
                    value === DEFAULT_ACCOUNT_VALUE ? "" : value,
                  )
                }
              >
                <SelectTrigger className="min-w-[12rem]" aria-label={NODE_LABELS[node] ?? node}>
                  <SelectValue placeholder="（默认首个账号）" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={DEFAULT_ACCOUNT_VALUE}>（默认首个账号）</SelectItem>
                  {accounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          );
        })}
        <div className="flex items-center gap-2">
          <Switch
            id="failover-enabled"
            checked={graphModels.failover_enabled !== false}
            onCheckedChange={(checked) => void setFailoverEnabled(checked)}
            aria-label="欠费自动换模"
          />
          <Label htmlFor="failover-enabled" className="cursor-pointer text-foreground">
            欠费自动换模
          </Label>
        </div>
        <div className="flex flex-col gap-2">
          <Label className="font-medium text-foreground">
            Failover 顺序（逗号分隔账号 id）
          </Label>
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
