import { FAQS } from "@/content/faq";
import { PRODUCT_POSITIONING, WORKFLOW_STEPS } from "@/content/product";
import { SEO, absoluteUrl, publicUrl } from "@/lib/seo";

export type NavItem = { name: string; url: string };

export function buildOrganizationSchema() {
  const home = absoluteUrl("/");
  const logo = publicUrl("assets/logo.webp");
  const image = publicUrl("assets/og-cover.png");

  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${home}#organization`,
    name: SEO.siteNameShort,
    alternateName: SEO.siteName,
    url: home,
    logo,
    image,
    description: SEO.defaultDescription,
    sameAs: [SEO.github],
    contactPoint: [
      {
        "@type": "ContactPoint",
        url: SEO.github,
        contactType: "customer support",
        availableLanguage: ["zh-CN", "zh"],
      },
    ],
    areaServed: ["CN"],
  };
}

export function buildSoftwareApplicationSchema() {
  const home = absoluteUrl("/");
  const image = publicUrl("assets/og-cover.png");

  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "@id": `${home}#software`,
    name: SEO.siteNameShort,
    applicationCategory: "BusinessApplication",
    applicationSubCategory: "E-commerce product research",
    operatingSystem: "Windows, macOS, Linux",
    softwareVersion: "0.1.0",
    inLanguage: SEO.language,
    description: SEO.defaultDescription,
    url: home,
    image,
    downloadUrl: SEO.releases,
    codeRepository: SEO.github,
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "CNY",
      description: "开源免费",
    },
    featureList: [
      "Agent 探索比价（规划、采集、配对、分析）",
      "闲鱼与 1688 双边市场数据采集",
      "高利润与热门选品机会发现",
      "利润测算与商品库沉淀",
      "价格与竞品监控",
      "本地优先数据存储",
    ],
    audience: {
      "@type": "Audience",
      audienceType: "电商卖家、闲鱼卖家、无货源新手、跨平台倒货商家",
    },
    author: { "@id": `${home}#organization` },
  };
}

export function buildFaqSchema() {
  const home = absoluteUrl("/");

  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "@id": `${home}#faq`,
    mainEntity: FAQS.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };
}

/** SpyX 风格 HowTo：含 HowToTool 与分步 HowToDirection。 */
export function buildHowToSchema() {
  const home = absoluteUrl("/");

  return {
    "@context": "https://schema.org",
    "@type": "HowTo",
    "@id": `${home}#howto`,
    name: "如何用叮答发现有利润的货",
    description: PRODUCT_POSITIONING.subtitle,
    tool: {
      "@type": "HowToTool",
      name: SEO.siteNameShort,
    },
    step: WORKFLOW_STEPS.map((step, index) => ({
      "@type": "HowToStep",
      position: String(index + 1),
      name: step.title,
      itemListElement: [
        {
          "@type": "HowToDirection",
          position: "1",
          text: step.desc,
        },
      ],
    })),
  };
}

export function buildSiteNavigationSchema(nav: NavItem[], sectionUrl?: string) {
  const home = absoluteUrl("/");

  return {
    "@context": "https://schema.org",
    "@type": "SiteNavigationElement",
    url: sectionUrl ? absoluteUrl(sectionUrl) : home,
    hasPart: nav.map((item) => ({
      "@type": "WebPage",
      name: item.name,
      url: item.url.startsWith("http") ? item.url : absoluteUrl(item.url),
    })),
  };
}

/** SpyX blogSchemaScript 同款 WebPage + ImageObject 图。 */
export function buildWebPageGraph(canonicalPath: string) {
  const canonicalUrl = absoluteUrl(canonicalPath);
  const home = absoluteUrl("/");
  const image = publicUrl("assets/og-cover.png");

  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": `${home}#website`,
        url: home,
        name: SEO.siteNameShort,
        alternateName: SEO.siteName,
        description: SEO.defaultDescription,
        inLanguage: SEO.language,
        publisher: { "@id": `${home}#organization` },
        potentialAction: {
          "@type": "SearchAction",
          target: {
            "@type": "EntryPoint",
            urlTemplate: `${absoluteUrl("/console/discovery/start/")}?q={search_term_string}`,
          },
          "query-input": "required name=search_term_string",
        },
      },
      {
        "@type": "ImageObject",
        "@id": `${canonicalUrl}#primaryimage`,
        inLanguage: SEO.language,
        url: image,
        contentUrl: image,
        width: 1200,
        height: 630,
      },
      {
        "@type": "WebPage",
        "@id": `${canonicalUrl}#webpage`,
        url: canonicalUrl,
        name: SEO.siteName,
        description: SEO.defaultDescription,
        inLanguage: SEO.language,
        isPartOf: { "@id": `${home}#website` },
        primaryImageOfPage: { "@id": `${canonicalUrl}#primaryimage` },
      },
    ],
  };
}

export function buildHomeJsonLd() {
  return {
    "@context": "https://schema.org",
    "@graph": [
      buildOrganizationSchema(),
      buildSoftwareApplicationSchema(),
      buildFaqSchema(),
      buildHowToSchema(),
    ],
  };
}
