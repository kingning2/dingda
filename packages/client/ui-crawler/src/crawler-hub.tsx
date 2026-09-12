import { useRef, useState } from "react";
import { Search } from "lucide-react";
import type { CrawlPlatform, CrawlSearchResponse } from "@v2/contracts/crawler";
import { CRAWL_PLATFORM_TABS } from "./mock-data";
import { CrawlerResults, CrawlerStatusBanner } from "./crawler-results";
import { searchCrawlerProductsLive } from "./crawler-api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@v2/ui-primitives/tabs";
import { Button } from "@v2/ui-primitives/button";
import { Input } from "@v2/ui-primitives/input";

interface CrawlerPanelProps {
  platform: CrawlPlatform;
}

export function CrawlerPanel({ platform }: CrawlerPanelProps) {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<CrawlSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function handleCrawl() {
    const trimmed = query.trim();
    if (!trimmed) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setResponse({
      task_id: `crawl-${platform}`,
      status: {
        state: "running",
        label: "爬取中",
        hint: "正在连接爬虫…",
        badge_class: "bg-sky-500/15 text-sky-600",
      },
      items: [],
      total: 0,
    });

    try {
      const result = await searchCrawlerProductsLive(
        { platform, query: trimmed, limit: 12 },
        {
          onStatus: (status) => {
            setResponse((prev) =>
              prev
                ? {
                    ...prev,
                    status: {
                      state: status.state,
                      label: status.label,
                      hint: status.hint ?? null,
                      badge_class:
                        status.state === "error"
                          ? "bg-destructive/15 text-destructive"
                          : "bg-sky-500/15 text-sky-600",
                    },
                    search_url: status.search_url ?? prev.search_url,
                  }
                : prev,
            );
          },
          onResult: (next) => setResponse(next),
          onError: (err) => setError(err.message),
        },
        { signal: controller.signal },
      );
      setResponse(result);
      if (result.status.state === "error" || result.error_code) {
        setError(result.message?.trim() || "爬取失败");
      }
    } catch (err) {
      if (controller.signal.aborted) return;
      const message = err instanceof Error ? err.message : "爬取失败";
      setError(message);
      setResponse((prev) =>
        prev
          ? {
              ...prev,
              status: {
                state: "error",
                label: "失败",
                hint: message,
                badge_class: "bg-destructive/15 text-destructive",
              },
            }
          : prev,
      );
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setLoading(false);
      }
    }
  }

  const platformLabel = CRAWL_PLATFORM_TABS.find((item) => item.id === platform)?.label ?? platform;
  const status = response?.status;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        在 {platformLabel} 按关键词直接爬取商品（真实 Python Crawler），不经过 AI 选品流程。
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

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {!loading && response && response.total > 0 ? (
        <p className="text-sm text-muted-foreground">共 {response.total} 条结果</p>
      ) : null}

      <CrawlerResults
        items={response?.items ?? []}
        loading={loading && (response?.items.length ?? 0) === 0}
      />
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
