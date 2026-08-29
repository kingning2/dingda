import { JsonLdScript } from "@/components/seo/json-ld-script";
import { buildWebPageGraph } from "@/lib/seo/schemas";

type WebPageJsonLdProps = {
  canonicalPath: string;
};

export function WebPageJsonLd({ canonicalPath }: WebPageJsonLdProps) {
  return <JsonLdScript data={buildWebPageGraph(canonicalPath)} />;
}
