import { JsonLdScript } from "@/components/seo/json-ld-script";
import { buildSiteNavigationSchema } from "@/lib/seo/schemas";
import type { NavItem } from "@/lib/seo/schemas";

type SiteNavigationJsonLdProps = {
  nav: NavItem[];
  sectionUrl?: string;
};

export function SiteNavigationJsonLd({ nav, sectionUrl }: SiteNavigationJsonLdProps) {
  return <JsonLdScript data={buildSiteNavigationSchema(nav, sectionUrl)} />;
}
