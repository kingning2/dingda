import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/discovery/start");

export default function DiscoveryStartLayout({ children }: { children: React.ReactNode }) {
  return children;
}
