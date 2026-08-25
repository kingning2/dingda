/**
 * 闲鱼商品管理页（迁移自原前端 `pages/items/Items.tsx`）。
 *
 * 按原前端核心交互重写：商品列表 + 关键词/账号筛选 + 擦亮/多规格标记 + AI 提示词编辑。
 * 数据访问走 Tauri IPC（`@desk/platform/ipc/item`），复用 crates/app ItemService。
 */

import { OWNER_ID } from "@desk/platform/constants";
import { useEffect, useState } from "react";
import {
  AsyncButton,
  Button,
  ConfirmModal,
  Input,
  Loading,
  PageCardGrid,
  PageGlowCard,
  PageScaffold,
  Pagination,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
  toast,
} from "@desk/ui";
import { Pencil, RefreshCw, Search } from "@desk/ui/icons";
import { itemDetailPath } from "@desk/platform/compile";
import { itemList, itemSync, itemUpdate, type Item } from "@desk/platform/ipc/item";
import { accountList, type XianyuAccount } from "@desk/platform/ipc/account";
import { useWorkspaceNav } from "../../../app/use-workspace-tabs";
import { formatAmount, getErrorMessage } from "@desk/utils";

const PAGE_SIZE = 20;

/**
 * 闲鱼商品管理页。
 *
 * @author agent
 * @created 2026-08-13
 */
export function XianyuItemsPage() {
  const { selectTab } = useWorkspaceNav();
  const [items, setItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [accounts, setAccounts] = useState<XianyuAccount[]>([]);
  const [accountId, setAccountId] = useState("all");
  const [editTarget, setEditTarget] = useState<Item | null>(null);
  const [aiPrompt, setAiPrompt] = useState("");
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);

  // 加载账号列表。
  useEffect(() => {
    let cancelled = false;
    void accountList(OWNER_ID)
      .then((list) => {
        if (!cancelled) {
          setAccounts(list);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          toast.error(getErrorMessage(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function load(nextPage = page) {
    setLoading(true);
    try {
      const [list, count] = await itemList({
        owner_id: OWNER_ID,
        page: nextPage,
        page_size: PAGE_SIZE,
        keyword: keyword.trim() || undefined,
        account_id: accountId === "all" ? undefined : accountId,
      });
      setItems(list);
      setTotal(count);
      setPage(nextPage);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void itemList({
      owner_id: OWNER_ID,
      page: 1,
      page_size: PAGE_SIZE,
      keyword: keyword.trim() || undefined,
      account_id: accountId === "all" ? undefined : accountId,
    })
      .then(([list, count]) => {
        if (cancelled) return;
        setItems(list);
        setTotal(count);
        setPage(1);
      })
      .catch((error) => {
        if (!cancelled) {
          toast.error(getErrorMessage(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await itemSync(
        OWNER_ID,
        accountId === "all" ? undefined : accountId,
      );
      toast.success(
        `同步完成：${result.synced} 件（新增 ${result.created}，更新 ${result.updated}）`,
      );
      await load(1);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setSyncing(false);
    }
  }

  async function handleSaveAiPrompt() {
    if (!editTarget) return;
    setSaving(true);
    try {
      await itemUpdate(OWNER_ID, editTarget.item_id, aiPrompt);
      toast.success("AI 提示词已保存");
      setEditTarget(null);
      await load();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageScaffold
      title="商品管理"
      subtitle="查看在售商品、按账号筛选，并维护智能回复说明"
      toolbar={
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <Input
              placeholder="搜索商品编号或标题"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void load(1);
              }}
              className="w-64"
            />
            <Button variant="outline" size="sm" onClick={() => void load(1)}>
              <Search className="size-3.5" aria-hidden />
              搜索
            </Button>
            <Select value={accountId} onValueChange={setAccountId}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="全部账号" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部账号</SelectItem>
                {accounts.map((account) => (
                  <SelectItem key={account.account_id} value={account.account_id}>
                    {account.display_name || account.account_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <AsyncButton
              variant="outline"
              size="sm"
              loading={syncing}
              disabled={loading}
              onClick={() => handleSync()}
            >
              <RefreshCw className="size-3.5" aria-hidden />
              同步商品
            </AsyncButton>
          </div>
          <span className="text-[length:var(--text-sm)] text-muted-foreground">
            共 {total} 件商品
          </span>
        </div>
      }
      footer={
        <Pagination page={page} totalPages={totalPages} onPageChange={(next) => void load(next)} />
      }
    >
      {loading ? (
        <Loading size="lg" text="加载中..." className="py-16" />
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-muted-foreground">暂无商品，请先同步闲鱼在售商品</p>
          <AsyncButton variant="outline" loading={syncing} onClick={() => handleSync()}>
            <RefreshCw className="size-4" aria-hidden />
            同步商品
          </AsyncButton>
        </div>
      ) : (
        <PageCardGrid>
            {items.map((item) => {
              const accountLabel =
                accounts.find((account) => account.account_id === item.account_id)?.display_name ||
                item.account_id;
              return (
                <PageGlowCard
                  key={item.item_id}
                  role="button"
                  tabIndex={0}
                  className="text-left transition hover:bg-muted/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => selectTab(itemDetailPath(item.item_id))}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      selectTab(itemDetailPath(item.item_id));
                    }
                  }}
                >
                  <div className="relative rounded-[inherit] border border-border bg-card p-4 transition hover:border-primary/40">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <div
                        className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-border bg-muted text-[length:var(--text-sm)] font-medium text-muted-foreground"
                        aria-hidden
                      >
                        {(item.title || item.item_id).slice(0, 1)}
                      </div>
                      <div className="min-w-0 space-y-1">
                        <div className="line-clamp-2 text-[length:var(--text-base)] font-medium leading-snug">
                          {item.title || "—"}
                        </div>
                        <div className="truncate font-mono text-[length:var(--text-xs)] text-muted-foreground">
                          {item.item_id}
                        </div>
                      </div>
                    </div>
                    <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[length:var(--text-xs)] font-medium text-primary">
                      {formatAmount(item.price)} 元
                    </span>
                  </div>

                  <div className="mt-4 space-y-2 text-[length:var(--text-sm)]">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-muted-foreground">所属账号</span>
                      <span className="truncate max-w-[65%] text-right">{accountLabel}</span>
                    </div>
                    <div className="flex items-start justify-between gap-3">
                      <span className="shrink-0 text-muted-foreground">AI 提示词</span>
                      <span className="line-clamp-2 max-w-[65%] text-right text-muted-foreground">
                        {item.ai_prompt || "—"}
                      </span>
                    </div>
                  </div>

                  {(item.is_polished || item.is_multi_spec || item.has_card) && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {item.is_polished ? (
                        <span className="rounded-full bg-blue-500/15 px-2 py-0.5 text-[length:var(--text-xs)] text-blue-500">
                          已擦亮
                        </span>
                      ) : null}
                      {item.is_multi_spec ? (
                        <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[length:var(--text-xs)] text-amber-500">
                          多规格
                        </span>
                      ) : null}
                      {item.has_card ? (
                        <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[length:var(--text-xs)] text-emerald-500">
                          有卡券
                        </span>
                      ) : null}
                    </div>
                  )}

                  <div className="mt-4 flex flex-wrap gap-2" onClick={(event) => event.stopPropagation()}>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => selectTab(itemDetailPath(item.item_id))}
                    >
                      查看详情
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setEditTarget(item);
                        setAiPrompt(item.ai_prompt);
                      }}
                    >
                      <Pencil className="size-3.5" aria-hidden />
                      AI 提示词
                    </Button>
                  </div>
                  </div>
                </PageGlowCard>
              );
            })}
          </PageCardGrid>
      )}

      {/* AI 提示词编辑弹窗 */}
      <ConfirmModal
        isOpen={editTarget !== null}
        title="编辑 AI 提示词"
        message={
          <div className="space-y-2 text-left">
            <p className="font-mono text-[length:var(--text-xs)] text-muted-foreground">
              {editTarget?.item_id} · {editTarget?.title}
            </p>
            <Textarea
              value={aiPrompt}
              onChange={(event) => setAiPrompt(event.target.value)}
              placeholder="商品特殊说明，如：不议价、现货直发"
              rows={4}
            />
          </div>
        }
        confirmText={saving ? "保存中…" : "保存"}
        loading={saving}
        onConfirm={() => void handleSaveAiPrompt()}
        onCancel={() => setEditTarget(null)}
      />
    </PageScaffold>
  );
}
