import { createPageMetadata } from "@/lib/seo";
import { HomeJsonLd } from "@/components/seo/json-ld";
import { PRODUCT_POSITIONING } from "@/content/product";
import type { Metadata } from "next";
import LandingPage from "./_components/landing-page";

export const metadata: Metadata = createPageMetadata({
  title: `叮答 DingDa — ${PRODUCT_POSITIONING.tagline}`,
  description: PRODUCT_POSITIONING.subtitle,
  path: "/",
});

export default function Page() {
  return (
    <>
      <HomeJsonLd />
      <LandingPage />
    </>
  );
}
