import type { Metadata } from "next";
import { PRODUCT_POSITIONING } from "@/content/product";
import { AI_CRAWLER_USER_AGENTS, GEO_FILES, GEO_PLATFORM_IDS, GEO_PRIMARY_PLATFORMS } from "@/lib/seo/ai-crawlers";
import { buildHomeJsonLd } from "@/lib/seo/schemas";
import { asset, basePath, siteUrl } from "@/lib/site";

const DEFAULT_SITE_URL = "https://kingning2.github.io/dingda";

export const SEO = {
  siteName: "叮答 DingDa",
  siteNameShort: "叮答",
  locale: "zh_CN",
  language: "zh-CN",
  twitterHandle: "@kingning2",
  github: "https://github.com/kingning2/dingda",
  releases: "https://github.com/kingning2/dingda/releases",
  defaultTitle: "叮答 DingDa — Agent 探索热门货，找出有利润的品",
  defaultDescription:
    "用 Agent + 爬虫在闲鱼与 1688 之间自动比价探索，帮商家和小白发现最近火的、有利润空间的商品。本地优先，数据在你手里，开源免费。",
  keywords: [
    "选品",
    "闲鱼选品",
    "1688选品",
    "无货源",
    "跨平台倒货",
    "Agent比价",
    "爬虫采集",
    "利润测算",
    "电商工具",
    "叮答",
    "DingDa",
    "本地优先",
    "Tauri",
  ],
} as const;

export function resolveSiteOrigin() {
  let url = siteUrl === "http://localhost:3200" ? DEFAULT_SITE_URL : siteUrl;
  url = url.replace(/\/+$/, "");
  if (basePath && url.endsWith(basePath)) {
    return url.slice(0, -basePath.length).replace(/\/+$/, "") || url;
  }
  return url;
}

/** @deprecated Use resolveSiteOrigin or absoluteUrl */
export function resolveSiteUrl() {
  return absoluteUrl("/").replace(/\/+$/, "");
}

export function absoluteUrl(path: string) {
  const origin = resolveSiteOrigin();
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${origin}${basePath}${normalized}`.replace(/([^:]\/)\/+/g, "$1");
}

/** 静态资源绝对 URL（含 basePath，避免与 absoluteUrl 重复拼接）。 */
export function publicUrl(relativePath: string) {
  return `${resolveSiteOrigin()}${asset(relativePath)}`.replace(/([^:]\/)\/+/g, "$1");
}

/** 全站发现性 URL（sitemap / robots / GEO 摘要）。 */
export const SITE_DISCOVERY_URLS = {
  robotsTxt: () => absoluteUrl("/robots.txt"),
  sitemap: () => absoluteUrl("/sitemap.xml"),
  llmsTxt: () => publicUrl(GEO_FILES.llms),
  aiGeo: () => publicUrl(GEO_FILES.aiGeo),
  doubaoGeo: () => publicUrl(GEO_FILES.doubaoGeo),
} as const;

/** 头条搜索站长平台（豆包/Bytespider 同源索引） */
export const TOUTIAO_WEBMASTER = {
  portal: "https://zhanzhang.toutiao.com/",
  verifyMetaName: "bytedance-verification-code",
  verifyFileName: "ByteDanceVerify.html",
  sitemapUrl: () => SITE_DISCOVERY_URLS.sitemap(),
} as const;

export const SITE_VERIFICATION = {
  google:
    process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION ??
    "cP79W1SgEeVV9gNafyqYLpUMVKK5oYM2Hj7R6YUKrvU",
  toutiao:
    process.env.NEXT_PUBLIC_TOUTIAO_SITE_VERIFICATION?.trim() ?? "qta2MU7bXS7qhnAiCMUM",
} as const;

/** 全站 GEO / 发现性元数据：写入 head，供搜索引擎与各 AI 爬虫读取。 */
export function siteDiscoveryMetadata(): Pick<Metadata, "alternates" | "other"> {
  const robotsTxt = SITE_DISCOVERY_URLS.robotsTxt();
  const sitemap = SITE_DISCOVERY_URLS.sitemap();
  const llmsTxt = SITE_DISCOVERY_URLS.llmsTxt();
  const aiGeo = SITE_DISCOVERY_URLS.aiGeo();
  const doubaoGeo = SITE_DISCOVERY_URLS.doubaoGeo();

  return {
    alternates: {
      types: {
        "text/markdown": llmsTxt,
        "text/plain": aiGeo,
      },
    },
    other: {
      "robots-txt": robotsTxt,
      "llms-txt": llmsTxt,
      sitemap,
      "ai-geo": aiGeo,
      "doubao-geo": doubaoGeo,
      "geo-primary": GEO_PRIMARY_PLATFORMS.join(","),
      "geo-platforms": GEO_PLATFORM_IDS.join(","),
      "ai-crawler": AI_CRAWLER_USER_AGENTS.join(","),
      "ai-crawler-policy": "allow",
      "toutiao-webmaster": TOUTIAO_WEBMASTER.portal,
      "toutiao-sitemap": sitemap,
    },
  };
}

function buildSiteVerification(): NonNullable<Metadata["verification"]> {
  const verification: NonNullable<Metadata["verification"]> = {
    google: SITE_VERIFICATION.google,
  };

  if (SITE_VERIFICATION.toutiao) {
    verification.other = {
      ...verification.other,
      [TOUTIAO_WEBMASTER.verifyMetaName]: SITE_VERIFICATION.toutiao,
    };
  }

  return verification;
}

export function createPageMetadata({
  title,
  description,
  path = "/",
  keywords,
  noIndex = false,
}: {
  title: string;
  description: string;
  path?: string;
  keywords?: string[];
  noIndex?: boolean;
}): Metadata {
  const url = absoluteUrl(path);
  const image = publicUrl("assets/og-cover.png");
  const discovery = siteDiscoveryMetadata();

  return {
    title,
    description,
    keywords: keywords ?? [...SEO.keywords],
    alternates: {
      canonical: url,
      languages: { "zh-CN": url },
      ...discovery.alternates,
    },
    other: discovery.other,
    robots: noIndex
      ? { index: false, follow: true, googleBot: { index: false, follow: true } }
      : {
          index: true,
          follow: true,
          googleBot: { index: true, follow: true, "max-image-preview": "large" },
        },
    openGraph: {
      type: "website",
      locale: SEO.locale,
      url,
      siteName: SEO.siteName,
      title,
      description,
      images: [
        {
          url: image,
          width: 1200,
          height: 630,
          alt: `${SEO.siteName} — ${PRODUCT_POSITIONING.tagline}`,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
    },
  };
}

const homePageMetadata = createPageMetadata({
  title: SEO.defaultTitle,
  description: SEO.defaultDescription,
  path: "/",
});

export const rootMetadata: Metadata = {
  metadataBase: new URL(absoluteUrl("/")),
  ...homePageMetadata,
  title: {
    template: `%s | ${SEO.siteName}`,
    default: SEO.defaultTitle,
  },
  authors: [{ name: SEO.siteName, url: SEO.github }],
  creator: SEO.siteName,
  publisher: SEO.siteName,
  category: "technology",
  applicationName: SEO.siteNameShort,
  formatDetection: { email: false, address: false, telephone: false },
  icons: {
    icon: asset("assets/logo.webp"),
    apple: asset("assets/logo.webp"),
    shortcut: asset("assets/logo.webp"),
  },
  verification: buildSiteVerification(),
};

export function buildJsonLd() {
  return buildHomeJsonLd();
}
