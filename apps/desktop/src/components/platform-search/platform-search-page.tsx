/**
 * 平台商品搜索页 — 通用壳：账号加载 / 搜索状态 / 结果列表容器。
 *
 * 平台差异（IPC、账号过滤、字段、文案）由 `PlatformSearchPageConfig` 注入，
 * 卡片渲染由 `renderOffer` 提供。搜索栏使用共享 `ChannelSearchToolbar`。
 */
import { OWNER_ID } from "@desk/platform/constants";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Loading, PageScaffold, toast } from "@desk/ui";
import { getErrorMessage } from "@desk/utils";
import { accountList, type XianyuAccount } from "@desk/platform/ipc/account";
import { ChannelSearchToolbar } from "@components/channel-search";


/** 搜索请求参数（对齐各平台 IPC）。 */
export interface SearchParams {
  ownerId: number;
  accountId: string;
  keyword: string;
  maxResults: number;
  headed: boolean;
}

/** 搜索响应公共字段。 */
export interface PlatformSearchResult {
  ok: boolean;
  detail?: string;
  keyword: string;
  total: number;
  totalBeforeFilter: number;
}

/** 平台搜索页配置 — 平台差异全部集中于此。 */
export interface PlatformSearchPageConfig<TItem, TResult extends PlatformSearchResult> {
  /** 账号过滤用的平台 id（`item.platform ?? "xianyu"`）。 */
  platform: string;
  search: (params: SearchParams) => Promise<TResult>;
  pageTitle: string;
  pageSubtitle: string;
  accountLabel: string;
  keywordPlaceholder: string;
  searchLabel?: string;
  accountEmptyText: string;
  noAccountError: string;
  /** 从响应提取结果数组。 */
  offersOf: (result: TResult) => TItem[];
  /** 渲染单个结果卡片（返回 `<li key=...>`）。 */
  renderOffer: (item: TItem) => ReactNode;
}

/** 平台商品搜索页。 */
export function PlatformSearchPage<TItem, TResult extends PlatformSearchResult>({
  config,
}: {
  config: PlatformSearchPageConfig<TItem, TResult>;
}) {
  const [accounts, setAccounts] = useState<XianyuAccount[]>([]);
  const [accountId, setAccountId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TResult | null>(null);

  const accountOptions = useMemo(
    () =>
      accounts.map((account) => ({
        id: account.account_id,
        label: account.display_name || account.login_id || account.account_id,
      })),
    [accounts],
  );

  useEffect(() => {
    let cancelled = false;
    void accountList(OWNER_ID)
      .then((list) => {
        if (cancelled) return;
        const filtered = list.filter(
          (item) => (item.platform ?? "xianyu") === config.platform && item.status === "active",
        );
        setAccounts(filtered);
        if (filtered.length > 0) {
          setAccountId((current) => current || filtered[0]!.account_id);
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
  }, [config.platform]);

  async function handleSearch() {
    const kw = keyword.trim();
    if (!kw) {
      toast.error("请输入搜索关键词");
      return;
    }
    if (!accountId) {
      toast.error(config.noAccountError);
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const data = await config.search({
        ownerId: OWNER_ID,
        accountId,
        keyword: kw,
        maxResults: 20,
        headed: true,
      });
      setResult(data);
      if (!data.ok) {
        toast.error(data.detail || "搜索未返回结果");
      } else {
        toast.success(`找到 ${data.total} 条结果`);
      }
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  const offers = result ? config.offersOf(result) : [];

  return (
    <PageScaffold
      title={config.pageTitle}
      subtitle={config.pageSubtitle}
      toolbar={
        <ChannelSearchToolbar
          accountLabel={config.accountLabel}
          accounts={accountOptions}
          accountId={accountId}
          onAccountIdChange={setAccountId}
          keyword={keyword}
          onKeywordChange={setKeyword}
          onSearch={() => void handleSearch()}
          loading={loading}
          keywordPlaceholder={config.keywordPlaceholder}
          searchLabel={config.searchLabel}
        />
      }
    >
      {accounts.length === 0 ? (
        <p className="text-sm text-muted-foreground">{config.accountEmptyText}</p>
      ) : null}

      {loading ? (
        <div className="flex justify-center py-12">
          <Loading text="正在启动浏览器并搜索…" />
        </div>
      ) : null}

      {result && offers.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            「{result.keyword}」共 {result.totalBeforeFilter} 条命中，展示 {result.total} 条
          </p>
          <ul className="space-y-3">{offers.map((item) => config.renderOffer(item))}</ul>
        </div>
      ) : null}

      {result && offers.length === 0 && !loading ? (
        <p className="text-sm text-muted-foreground">{result.detail || "暂无结果"}</p>
      ) : null}
    </PageScaffold>
  );
}
