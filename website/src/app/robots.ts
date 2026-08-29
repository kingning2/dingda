import type { MetadataRoute } from "next";
import { buildAllRobotsRules } from "@/lib/seo/robots-config";
import { absoluteUrl } from "@/lib/seo";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: buildAllRobotsRules(),
    sitemap: absoluteUrl("/sitemap.xml"),
    host: absoluteUrl("/"),
  };
}
