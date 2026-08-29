import { DashboardSkeleton } from "@/components/business/dashboard-skeleton";
import { WebPageJsonLd } from "@/components/seo/web-page-json-ld";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console", { noIndex: false });

export default function ConsolePage() {
  return (
    <>
      <WebPageJsonLd canonicalPath="/console/" />
      <DashboardSkeleton />
    </>
  );
}