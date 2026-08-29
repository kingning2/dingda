import { WORKSPACE_NAV } from "@/content/business";
import { SEO } from "@/lib/seo";
import type { NavItem } from "@/lib/seo/schemas";

/** 营销站主导航 — 用于 SiteNavigationElement JSON-LD。 */
export const MARKETING_NAV: NavItem[] = [
  { name: "首页", url: "/" },
  { name: "怎么工作", url: "/#how" },
  { name: "功能", url: "/#features" },
  { name: "常见问题", url: "/#faq" },
  { name: "常见问题", url: "/faq/" },
  { name: "控制台演示", url: "/console/" },
  { name: "下载", url: SEO.releases },
  { name: "GitHub", url: SEO.github },
];

function flattenWorkspaceNav(): NavItem[] {
  const items: NavItem[] = [{ name: "工作台总览", url: "/console/" }];

  for (const group of WORKSPACE_NAV) {
    for (const item of group.items) {
      if ("url" in item && item.url) {
        items.push({ name: item.title, url: `${item.url}/` });
      }
      if ("children" in item && item.children) {
        for (const child of item.children) {
          items.push({ name: child.title, url: `${child.url}/` });
        }
      }
    }
  }

  const seen = new Set<string>();
  return items.filter((entry) => {
    if (seen.has(entry.url)) return false;
    seen.add(entry.url);
    return true;
  });
}

/** 控制台演示导航 — 用于 SiteNavigationElement JSON-LD。 */
export const CONSOLE_NAV = flattenWorkspaceNav();
