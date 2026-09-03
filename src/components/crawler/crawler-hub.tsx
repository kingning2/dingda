import { useState } from "react";
import { Search } from "lucide-react";
import type { CrawlPlatform, CrawlSearchResponse } from "@/contracts/crawler";
import { CRAWL_PLATFORM_TABS, mockCrawlSearchApi } from "./mock-data";
import { CrawlerResults, CrawlerStatusBanner } from "./crawler-results";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface CrawlerPanelProps {
  platform: CrawlPlatform;
}

export function CrawlerPanel({ platform }: CrawlerPanelProps) {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<CrawlSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCrawl() {
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }

    setLoading(true);
    setResponse(null);

    try {
      const result = await mockCrawlSearchApi(
        { platform, query: trimmed },
        (progress) => setResponse(progress),
      );
      setResponse(result);
    } finally {
      setLoading(false);
    }
  }

  const platformLabel = CRAWL_PLATFORM_TABS.find((item) => item.id === platform)?.label ?? platform;
  const status = response?.status;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        在 {platformLabel} 按关键词直接爬取商品，不经过 AI 选品流程。
      </p>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={`输入想查看的商品，例如：${platform === "ali1688" ? "USB小风扇" : "露营椅"}`}
          className="flex-1"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void handleCrawl();
            }
          }}
        />
        <Button onClick={() => void handleCrawl()} disabled={!query.trim() || loading}>
          <Search className="size-4" />
          开始爬取
        </Button>
      </div>

      {status ? (
        <CrawlerStatusBanner
          label={status.label}
          hint={status.hint}
          badgeClass={status.badge_class}
        />
      ) : null}

      {!loading && response && response.total > 0 ? (
        <p className="text-sm text-muted-foreground">共 {response.total} 条结果</p>
      ) : null}

      <CrawlerResults items={response?.items ?? []} loading={loading} />
    </div>
  );
}

interface CrawlerHubProps {
  initialPlatform?: CrawlPlatform;
}

export function CrawlerHub({ initialPlatform = "xianyu" }: CrawlerHubProps) {
  const [platform, setPlatform] = useState<CrawlPlatform>(initialPlatform);

  return (
    <div className="flex min-h-0 flex-col gap-1">
      <Tabs value={platform} onValueChange={(value) => setPlatform(value as CrawlPlatform)}>
        <TabsList aria-label="爬虫平台">
          {CRAWL_PLATFORM_TABS.map((item) => (
            <TabsTrigger key={item.id} value={item.id}>
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {CRAWL_PLATFORM_TABS.map((item) => (
          <TabsContent key={item.id} value={item.id}>
            <CrawlerPanel platform={item.id} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
