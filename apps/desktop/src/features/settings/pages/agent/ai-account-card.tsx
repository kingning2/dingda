/**
 * 单 AI 账号卡片 — 展示余额、密钥摘要与操作。
 */

import { useCallback, useEffect, useState } from "react";
import { Button, PageGlowCard } from "@desk/ui";
import { Pencil, RefreshCw, Trash2 } from "@desk/ui/icons";
import type { AiAccount, AiProvider } from "@desk/contracts";
import { aiAccountBalance, type AiBalanceInfoDto } from "@desk/platform/ipc/ai";
import { providerSupportsBalance } from "./use-ai-config";

function maskKey(key: string): string {
  if (!key) return "—";
  if (key.length <= 8) return "••••••••";
  return `${key.slice(0, 3)}••••••••${key.slice(-4)}`;
}

function pickBalance(balances: AiBalanceInfoDto[]): AiBalanceInfoDto | null {
  return balances.find((item) => item.currency === "CNY") ?? balances[0] ?? null;
}

function formatMoney(currency: string, amount: string): string {
  const value = Number.parseFloat(amount);
  if (Number.isNaN(value)) {
    return amount;
  }
  const symbol = currency === "CNY" ? "¥" : currency === "USD" ? "$" : `${currency} `;
  return `${symbol}${value.toFixed(2)}`;
}

export interface AiAccountCardProps {
  account: AiAccount;
  provider: AiProvider | undefined;
  onEdit: () => void;
  onDelete: () => void;
}

export function AiAccountCard({ account, provider, onEdit, onDelete }: AiAccountCardProps) {
  const supportsBalance = providerSupportsBalance(provider);
  const [balanceText, setBalanceText] = useState("加载中…");
  const [balanceHint, setBalanceHint] = useState<string | null>(null);
  const [loadingBalance, setLoadingBalance] = useState(false);

  const loadBalance = useCallback(async () => {
    if (!supportsBalance || !provider) {
      setBalanceText("—");
      setBalanceHint(null);
      return;
    }

    setLoadingBalance(true);
    try {
      const result = await aiAccountBalance(provider.base_url ?? "", account.api_key);
      if (!result.ok) {
        setBalanceText("—");
        setBalanceHint("暂时无法查询余额");
        return;
      }
      const primary = pickBalance(result.balances);
      if (!primary) {
        setBalanceText("—");
        setBalanceHint(null);
        return;
      }
      setBalanceText(formatMoney(primary.currency, primary.total_balance));
      setBalanceHint(result.is_available ? null : "余额可能不足，请及时充值");
    } catch {
      setBalanceText("—");
      setBalanceHint("暂时无法查询余额");
    } finally {
      setLoadingBalance(false);
    }
  }, [account.api_key, provider, supportsBalance]);

  useEffect(() => {
    void loadBalance();
  }, [loadBalance]);

  return (
    <PageGlowCard className="border border-border/70 bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium text-foreground">{account.name}</p>
          <p className="truncate text-[length:var(--text-xs)] text-muted-foreground">
            {provider?.name ?? account.provider_id}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {supportsBalance ? (
            <Button
              size="icon"
              variant="ghost"
              aria-label="刷新余额"
              disabled={loadingBalance}
              onClick={() => void loadBalance()}
            >
              <RefreshCw
                className={`size-3.5 ${loadingBalance ? "animate-spin" : ""}`}
                aria-hidden
              />
            </Button>
          ) : null}
          <Button size="icon" variant="ghost" aria-label="编辑" onClick={onEdit}>
            <Pencil className="size-3.5" aria-hidden />
          </Button>
          <Button size="icon" variant="ghost" aria-label="删除" onClick={onDelete}>
            <Trash2 className="size-3.5" aria-hidden />
          </Button>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {supportsBalance ? (
          <div>
            <p className="text-[length:var(--text-xs)] text-muted-foreground">剩余余额</p>
            <p className="mt-0.5 text-[length:var(--text-lg)] font-semibold tracking-tight">
              {balanceText}
            </p>
            {balanceHint ? (
              <p className="text-[length:var(--text-xs)] text-muted-foreground">{balanceHint}</p>
            ) : null}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[length:var(--text-xs)] text-muted-foreground">
          <span>密钥 {maskKey(account.api_key)}</span>
          {account.default_model ? <span>常用模型 {account.default_model}</span> : null}
        </div>
      </div>
    </PageGlowCard>
  );
}
