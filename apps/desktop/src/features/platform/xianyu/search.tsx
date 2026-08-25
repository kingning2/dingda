/**
 * 闲鱼商品搜索页 — 平台配置 + 结果卡片；壳复用共享 `PlatformSearchPage`。
 */
import type { ReactNode } from "react";
import { ExternalLink } from "@desk/ui/icons";
import {
  PlatformSearchPage,
  type PlatformSearchPageConfig,
} from "@components/platform-search";
import {
  xianyuSearch,
  type XianyuSearchItem,
  type XianyuSearchResponse,
} from "@desk/platform/ipc/xianyu-search";

function formatPrice(item: XianyuSearchItem): string {
  const text = item.price?.text?.trim();
  if (text) return text;
  return "—";
}

function renderOffer(item: XianyuSearchItem): ReactNode {
  return (
    <li key={item.itemId}>
      <article className="flex gap-3 rounded-xl border border-border bg-card p-3 sm:gap-4 sm:p-4">
        {item.image ? (
          <img
            src={item.image}
            alt=""
            className="size-20 shrink-0 rounded-md bg-muted object-cover sm:size-24"
            loading="lazy"
          />
        ) : (
          <div className="size-20 shrink-0 rounded-md bg-muted sm:size-24" />
        )}
        <div className="min-w-0 flex-1 space-y-1.5">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="line-clamp-2 text-sm font-medium leading-snug hover:underline"
          >
            {item.title}
          </a>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="text-base font-semibold text-foreground">{formatPrice(item)}</span>
            {item.seller?.name ? <span>{item.seller.name}</span> : null}
            {item.location ? <span>{item.location}</span> : null}
            {item.wantCount ? <span>{item.wantCount} 人想要</span> : null}
            {item.publishedAt ? <span>{item.publishedAt}</span> : null}
          </div>
          {item.tags && item.tags.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {item.tags.slice(0, 4).map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground"
                >
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="hidden shrink-0 self-start text-muted-foreground hover:text-foreground sm:block"
          aria-label="在新窗口打开"
        >
          <ExternalLink className="size-4" />
        </a>
      </article>
    </li>
  );
}

const config: PlatformSearchPageConfig<XianyuSearchItem, XianyuSearchResponse> = {
  platform: "xianyu",
  search: (params) => xianyuSearch(params),
  pageTitle: "闲鱼商品搜索",
  pageSubtitle: "在闲鱼搜索二手商品（会弹出浏览器窗口完成搜索）",
  accountLabel: "闲鱼账号",
  keywordPlaceholder: "例如：iPhone 15",
  searchLabel: "搜索",
  accountEmptyText: "请先在「账号管理」扫码登录闲鱼账号。",
  noAccountError: "请先添加并选择闲鱼账号",
  offersOf: (result) => result.offers,
  renderOffer,
};

/** 闲鱼商品搜索页。 */
export function XianyuSearchPage() {
  return <PlatformSearchPage config={config} />;
}
