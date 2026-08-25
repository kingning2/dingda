/**
 * 1688 商品搜索页 — 平台配置 + 结果卡片；壳复用共享 `PlatformSearchPage`。
 */
import type { ReactNode } from "react";
import { ExternalLink } from "@desk/ui/icons";
import {
  PlatformSearchPage,
  type PlatformSearchPageConfig,
} from "@components/platform-search";
import {
  ali1688Search,
  type Ali1688SearchOffer,
  type Ali1688SearchResponse,
} from "@desk/platform/ipc/ali1688-search";

function formatPrice(offer: Ali1688SearchOffer): string {
  const text = offer.price?.text?.trim();
  if (text) return text;
  const min = offer.price?.min;
  if (typeof min === "number") return `¥${min}`;
  return "—";
}

function formatLocation(offer: Ali1688SearchOffer): string {
  const province = offer.location?.province?.trim();
  const city = offer.location?.city?.trim();
  if (province && city) return `${province} · ${city}`;
  return province || city || "—";
}

function renderOffer(offer: Ali1688SearchOffer): ReactNode {
  return (
    <li key={offer.offerId}>
      <article className="flex gap-3 rounded-xl border border-border bg-card p-3 sm:gap-4 sm:p-4">
        {offer.image ? (
          <img
            src={offer.image}
            alt=""
            className="size-20 shrink-0 rounded-md bg-muted object-cover sm:size-24"
            loading="lazy"
          />
        ) : (
          <div className="size-20 shrink-0 rounded-md bg-muted sm:size-24" />
        )}
        <div className="min-w-0 flex-1 space-y-1.5">
          <a
            href={offer.url}
            target="_blank"
            rel="noreferrer"
            className="line-clamp-2 text-sm font-medium leading-snug hover:underline"
          >
            {offer.title}
          </a>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="text-base font-semibold text-foreground">{formatPrice(offer)}</span>
            <span>{offer.supplier?.name ?? "—"}</span>
            <span>{formatLocation(offer)}</span>
            {offer.turnover ? <span>成交 {offer.turnover}</span> : null}
          </div>
          {offer.tags && offer.tags.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {offer.tags.slice(0, 4).map((tag) => (
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
          href={offer.url}
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

const config: PlatformSearchPageConfig<Ali1688SearchOffer, Ali1688SearchResponse> = {
  platform: "ali1688",
  search: (params) => ali1688Search(params),
  pageTitle: "商品搜索",
  pageSubtitle: "在 1688 搜索批发商品（会弹出浏览器窗口完成搜索）",
  accountLabel: "1688 账号",
  keywordPlaceholder: "例如：苹果17pro",
  accountEmptyText: "请先在「账号管理」扫码登录 1688 账号。",
  noAccountError: "请先添加并选择 1688 账号",
  offersOf: (result) => result.offers,
  renderOffer,
};

/** 1688 商品搜索页。 */
export function Ali1688SearchPage() {
  return <PlatformSearchPage config={config} />;
}
