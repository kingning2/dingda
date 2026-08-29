import { JsonLdScript } from "@/components/seo/json-ld-script";
import { SiteNavigationJsonLd } from "@/components/seo/site-navigation-json-ld";
import { WebPageJsonLd } from "@/components/seo/web-page-json-ld";
import { buildHomeJsonLd } from "@/lib/seo/schemas";
import { MARKETING_NAV } from "@/lib/seo/navigation";

/** 营销首页 JSON-LD（Organization / SoftwareApplication / FAQ / HowTo + 导航 + WebPage 图）。 */
export function HomeJsonLd() {
  return (
    <>
      <JsonLdScript data={buildHomeJsonLd()} />
      <SiteNavigationJsonLd nav={MARKETING_NAV} />
      <WebPageJsonLd canonicalPath="/" />
    </>
  );
}
