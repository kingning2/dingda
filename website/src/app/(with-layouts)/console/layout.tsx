import { JsonLdScript } from "@/components/seo/json-ld-script";
import { SiteNavigationJsonLd } from "@/components/seo/site-navigation-json-ld";
import { CONSOLE_NAV } from "@/lib/seo/navigation";
import { buildSoftwareApplicationSchema } from "@/lib/seo/schemas";
import type { Metadata } from "next";

/** 控制台子页为演示骨架，默认不收录；首页 /console/ 在 page.tsx 单独放开。 */
export const metadata: Metadata = {
  robots: { index: false, follow: true, googleBot: { index: false, follow: true } },
};

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <JsonLdScript data={buildSoftwareApplicationSchema()} />
      <SiteNavigationJsonLd nav={CONSOLE_NAV} sectionUrl="/console/" />
      {children}
    </>
  );
}
