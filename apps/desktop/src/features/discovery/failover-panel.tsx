/**
 * 比价页右侧栏 — 欠费换模顺序与节点默认账号（可收起）。
 */

import { useEffect } from "react";
import {
  Button,
  IconButton,
  Label,
  Loading,
  ScrollArea,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
} from "@desk/ui";
import { ChevronDown, ChevronUp, Key, PanelRightClose, RefreshCw, X } from "@desk/ui/icons";
import { AI_GRAPH_NODES, useAiConfigStore } from "@feature/agent/use-ai-config";

const NODE_LABELS: Record<string, string> = {
  web_research: "网页调研",
  article_analyze: "文章分析",
  planner: "规划",
  analyze: "核验分析",
  finalize: "成文",
};

const DEFAULT_ACCOUNT = "__default__";

export interface FailoverPanelProps {
  /** 收起侧栏。 */
  onClose?: () => void;
}

/** 欠费换模与节点模型配置侧栏。 */
export function FailoverPanel({ onClose }: FailoverPanelProps) {
  const accounts = useAiConfigStore((state) => state.accounts);
  const graphModels = useAiConfigStore((state) => state.graphModels);
  const loading = useAiConfigStore((state) => state.loading);
  const loaded = useAiConfigStore((state) => state.loaded);
  const loadError = useAiConfigStore((state) => state.error);
  const load = useAiConfigStore((state) => state.load);
  const setGraphNodeAccount = useAiConfigStore((state) => state.setGraphNodeAccount);
  const setFailoverEnabled = useAiConfigStore((state) => state.setFailoverEnabled);
  const setFailoverAccountIds = useAiConfigStore((state) => state.setFailoverAccountIds);

  useEffect(() => {
    if (!loaded && !loading) {
      void load();
    }
  }, [loaded, loading, load]);

  const failoverEnabled = graphModels.failover_enabled !== false;
  const orderedIds = graphModels.failover_account_ids ?? [];
  const orderedAccounts = orderedIds
    .map((id) => accounts.find((account) => account.id === id))
    .filter((account): account is NonNullable<typeof account> => Boolean(account));
  const unusedAccounts = accounts.filter((account) => !orderedIds.includes(account.id));

  async function move(id: string, delta: -1 | 1) {
    const next = [...orderedIds];
    const index = next.indexOf(id);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= next.length) {
      return;
    }
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item);
    await setFailoverAccountIds(next);
  }

  async function addToFailover(id: string) {
    if (orderedIds.includes(id)) {
      return;
    }
    await setFailoverAccountIds([...orderedIds, id]);
  }

  async function removeFromFailover(id: string) {
    await setFailoverAccountIds(orderedIds.filter((item) => item !== id));
  }

  async function addAllAccounts() {
    await setFailoverAccountIds(accounts.map((account) => account.id));
  }

  return (
    <aside className="flex w-[min(100%,17.5rem)] shrink-0 flex-col border-l border-border/60">
      <div className="flex items-start justify-between gap-2 border-b border-border/60 px-3 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <RefreshCw className="size-4 shrink-0 text-primary" aria-hidden />
            <h2 className="text-[length:var(--text-sm)] font-semibold text-foreground">欠费换模</h2>
          </div>
          <p className="mt-1 text-[length:var(--text-xs)] text-muted-foreground">
            没额度时按顺序换下一个模型
          </p>
        </div>
        {onClose ? (
          <IconButton label="收起" className="shrink-0" onClick={onClose}>
            <PanelRightClose className="size-4" aria-hidden />
          </IconButton>
        ) : null}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-5 p-3">
          {loading && !loaded ? <Loading text="加载配置…" /> : null}
          {loadError ? (
            <p className="text-[length:var(--text-xs)] text-destructive">{loadError}</p>
          ) : null}

          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <Label htmlFor="failover-enabled" className="font-medium text-foreground">
                启用自动换模
              </Label>
              <p className="text-[length:var(--text-xs)] text-muted-foreground">
                余额不足时自动切换
              </p>
            </div>
            <Switch
              id="failover-enabled"
              checked={failoverEnabled}
              onCheckedChange={(checked) => void setFailoverEnabled(checked)}
              aria-label="启用自动换模"
            />
          </div>

          <section className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-[length:var(--text-xs)] font-medium uppercase tracking-wide text-muted-foreground">
                换模顺序
              </h3>
              {accounts.length > 0 ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={!failoverEnabled}
                  onClick={() => void addAllAccounts()}
                >
                  全部加入
                </Button>
              ) : null}
            </div>

            {accounts.length === 0 ? (
              <div className="py-4 text-center">
                <Key className="mx-auto size-4 text-muted-foreground" aria-hidden />
                <p className="mt-2 text-[length:var(--text-xs)] text-muted-foreground">
                  还没有 AI 账号，请先到「AI 配置」添加
                </p>
              </div>
            ) : null}

            {orderedAccounts.length === 0 && accounts.length > 0 ? (
              <p className="text-[length:var(--text-xs)] text-muted-foreground">
                尚未指定备用账号，可从下方列表加入
              </p>
            ) : null}

            <ul className="space-y-1">
              {orderedAccounts.map((account, index) => (
                <li
                  key={account.id}
                  className="flex items-center gap-1 border-b border-border/40 py-1.5 last:border-b-0"
                >
                  <span className="w-4 shrink-0 text-center text-[length:var(--text-xs)] text-muted-foreground">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1 px-1">
                    <p className="truncate text-[length:var(--text-sm)] font-medium text-foreground">
                      {account.name}
                    </p>
                    <p className="truncate text-[length:var(--text-xs)] text-muted-foreground">
                      {account.default_model || "默认模型"}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col">
                    <IconButton
                      label="上移"
                      className="size-6"
                      disabled={!failoverEnabled || index === 0}
                      onClick={() => void move(account.id, -1)}
                    >
                      <ChevronUp className="size-3.5" aria-hidden />
                    </IconButton>
                    <IconButton
                      label="下移"
                      className="size-6"
                      disabled={!failoverEnabled || index === orderedAccounts.length - 1}
                      onClick={() => void move(account.id, 1)}
                    >
                      <ChevronDown className="size-3.5" aria-hidden />
                    </IconButton>
                  </div>
                  <IconButton
                    label="移除"
                    className="size-7"
                    disabled={!failoverEnabled}
                    onClick={() => void removeFromFailover(account.id)}
                  >
                    <X className="size-3.5" aria-hidden />
                  </IconButton>
                </li>
              ))}
            </ul>

            {unusedAccounts.length > 0 ? (
              <div className="space-y-1 pt-1">
                <p className="text-[length:var(--text-xs)] text-muted-foreground">可加入</p>
                {unusedAccounts.map((account) => (
                  <button
                    key={account.id}
                    type="button"
                    disabled={!failoverEnabled}
                    className="flex w-full items-center justify-between gap-2 py-1.5 text-left text-[length:var(--text-sm)] text-foreground transition-colors hover:text-primary disabled:opacity-50"
                    onClick={() => void addToFailover(account.id)}
                  >
                    <span className="min-w-0 truncate">{account.name}</span>
                    <span className="shrink-0 text-[length:var(--text-xs)] text-primary">加入</span>
                  </button>
                ))}
              </div>
            ) : null}
          </section>

          <section className="space-y-3 border-t border-border/60 pt-4">
            <div className="space-y-1">
              <h3 className="text-[length:var(--text-xs)] font-medium uppercase tracking-wide text-muted-foreground">
                节点默认账号
              </h3>
              <p className="text-[length:var(--text-xs)] text-muted-foreground">
                各 AI 步骤优先使用的账号
              </p>
            </div>
            {AI_GRAPH_NODES.map((node) => {
              const current =
                graphModels.node_accounts?.find((row) => row.node === node)?.account_id ||
                DEFAULT_ACCOUNT;
              return (
                <div key={node} className="space-y-1.5">
                  <Label htmlFor={`node-account-${node}`}>{NODE_LABELS[node] ?? node}</Label>
                  <Select
                    value={current}
                    onValueChange={(value) =>
                      void setGraphNodeAccount(node, value === DEFAULT_ACCOUNT ? "" : value)
                    }
                  >
                    <SelectTrigger id={`node-account-${node}`} className="w-full">
                      <SelectValue placeholder="默认首个账号" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={DEFAULT_ACCOUNT}>（默认首个账号）</SelectItem>
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
          </section>
        </div>
      </ScrollArea>
    </aside>
  );
}
