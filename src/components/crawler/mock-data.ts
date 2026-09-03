import type {
  CrawlHistoryItem,
  CrawlPlatform,
  CrawlProductItem,
  CrawlSearchRequest,
  CrawlSearchResponse,
} from "@/contracts/crawler";

export const CRAWL_PLATFORM_TABS = [
  { id: "xianyu" as const, label: "闲鱼" },
  { id: "ali1688" as const, label: "1688" },
  { id: "xiaohongshu" as const, label: "小红书" },
];

const MOCK_RESULTS: Record<CrawlPlatform, CrawlProductItem[]> = {
  xianyu: [
    {
      id: "xy-1",
      title: "二手戴森吹风机 HD08 国行",
      price: "¥1,280",
      platform: "xianyu",
      seller: "数码回血小店",
      location: "上海",
      crawled_at: "2026-09-01T09:00:00+08:00",
    },
    {
      id: "xy-2",
      title: "九成新 Switch OLED 白色",
      price: "¥1,650",
      platform: "xianyu",
      seller: "游戏玩家阿杰",
      location: "杭州",
      crawled_at: "2026-09-01T09:00:00+08:00",
    },
    {
      id: "xy-3",
      title: "露营折叠椅 两把装",
      price: "¥89",
      platform: "xianyu",
      seller: "户外装备铺",
      location: "广州",
      crawled_at: "2026-09-01T09:00:00+08:00",
    },
  ],
  ali1688: [
    {
      id: "1688-1",
      title: "USB 小风扇 桌面款 批发",
      price: "¥12.5起",
      platform: "ali1688",
      seller: "义乌小家电厂",
      location: "浙江义乌",
      crawled_at: "2026-09-01T09:00:00+08:00",
    },
    {
      id: "1688-2",
      title: "宠物自动喂食器 代工",
      price: "¥68起",
      platform: "ali1688",
      seller: "深圳宠物科技",
      location: "广东深圳",
      crawled_at: "2026-09-01T09:00:00+08:00",
    },
  ],
  xiaohongshu: [
    {
      id: "xhs-1",
      title: "秋冬羊毛大衣穿搭笔记同款",
      price: "¥399",
      platform: "xiaohongshu",
      seller: "穿搭日记",
      crawled_at: "2026-09-01T09:00:00+08:00",
    },
    {
      id: "xhs-2",
      title: "平价护肤套装测评",
      price: "¥129",
      platform: "xiaohongshu",
      seller: "成分党小鹿",
      crawled_at: "2026-09-01T09:00:00+08:00",
    },
  ],
};

/** 模拟后端：爬取进行中的完整响应快照。 */
function mockBackendRunningResponse(taskId: string): CrawlSearchResponse {
  return {
    task_id: taskId,
    status: {
      state: "running",
      label: "爬取中",
      hint: "正在拉取商品列表…",
      badge_class: "bg-sky-500/15 text-sky-600",
    },
    items: [],
    total: 0,
  };
}

/** 模拟后端：爬取成功的完整响应快照。 */
function mockBackendSuccessResponse(taskId: string, platform: CrawlPlatform, query: string): CrawlSearchResponse {
  const keyword = query.trim().toLowerCase();
  const pool = MOCK_RESULTS[platform];
  const items = keyword
    ? pool.filter(
        (item) =>
          item.title.toLowerCase().includes(keyword) ||
          item.seller?.toLowerCase().includes(keyword),
      )
    : pool;
  const resolved = items.length > 0 ? items : pool.slice(0, 2);

  return {
    task_id: taskId,
    status: {
      state: "success",
      label: "已完成",
      hint: null,
      badge_class: "bg-emerald-500/15 text-emerald-600",
    },
    items: resolved,
    total: items.length > 0 ? items.length : pool.length,
  };
}

/**
 * 模拟 crawler_search API（占位，未接 Python）。
 * onUpdate 用于推送进行中的后端响应（轮询 / SSE 时同理）。
 */
export async function mockCrawlSearchApi(
  request: CrawlSearchRequest,
  onUpdate?: (response: CrawlSearchResponse) => void,
): Promise<CrawlSearchResponse> {
  const taskId = `task-${Date.now()}`;
  onUpdate?.(mockBackendRunningResponse(taskId));

  await new Promise((resolve) => {
    window.setTimeout(resolve, 900);
  });

  return mockBackendSuccessResponse(taskId, request.platform, request.query);
}

export const MOCK_CRAWL_HISTORY: CrawlHistoryItem[] = [
  {
    id: "hist-1",
    platform: "xianyu",
    query: "露营椅",
    total: 24,
    status: {
      state: "success",
      label: "已完成",
      hint: null,
      badge_class: "bg-emerald-500/15 text-emerald-600",
    },
    created_at: "2026-08-31T18:20:00+08:00",
  },
  {
    id: "hist-2",
    platform: "ali1688",
    query: "USB风扇",
    total: 56,
    status: {
      state: "success",
      label: "已完成",
      hint: null,
      badge_class: "bg-emerald-500/15 text-emerald-600",
    },
    created_at: "2026-08-31T16:05:00+08:00",
  },
];
