import type {
  AgentWorkDetailView,
  AgentWorkProductItem,
  AgentWorkStatusView,
} from "@/contracts/ai-work";

function status(
  state: string,
  label: string,
  badge_class: string,
  hint?: string | null,
): AgentWorkStatusView {
  return { state, label, badge_class, hint };
}

/** Demo：小红书搜索结果样例（右侧结果面板 / 对话商品条可复用）。 */
export const MOCK_XHS_PRODUCTS: AgentWorkProductItem[] = [
  {
    id: "6a967eaf000000002b0257e0",
    title: "爱做测试的进，小红书测试工具大合集",
    price: "—",
    platform: "xiaohongshu",
    seller: "测试笔记菌",
    image_url: undefined,
    product_url: "https://www.xiaohongshu.com/explore/6a967eaf000000002b0257e0",
    xsec_token: "mock-token-1",
    crawled_at: "2026-09-08T01:00:00.000Z",
    step_id: "step-search",
    step_label: "在小红书搜索「测试」",
  },
  {
    id: "6a88007d000000002a02d48d",
    title: "心理测试：你适合做什么副业？",
    price: "—",
    platform: "xiaohongshu",
    seller: "职场测评君",
    image_url: undefined,
    product_url: "https://www.xiaohongshu.com/explore/6a88007d000000002a02d48d",
    xsec_token: "mock-token-2",
    crawled_at: "2026-09-08T01:00:00.000Z",
    step_id: "step-search",
    step_label: "在小红书搜索「测试」",
  },
  {
    id: "6a7d44b000000000280308af",
    title: "666粉账号，为什么有人买1.99元趣味测试？",
    price: "—",
    platform: "xiaohongshu",
    seller: "AI小生意研究所",
    image_url: undefined,
    product_url: "https://www.xiaohongshu.com/explore/6a7d44b000000000280308af",
    xsec_token: "mock-token-3",
    crawled_at: "2026-09-08T01:00:00.000Z",
    step_id: "step-search",
    step_label: "在小红书搜索「测试」",
  },
];

/** Demo：闲鱼搜品样例。 */
export const MOCK_XIANYU_PRODUCTS: AgentWorkProductItem[] = [
  {
    id: "xy-1001",
    title: "几乎全新露营椅 承重120kg",
    price: "¥89",
    platform: "xianyu",
    seller: "山系玩家",
    location: "杭州",
    want_count: "12",
    product_url: "https://www.goofish.com/item?id=xy-1001",
    crawled_at: "2026-09-08T01:00:00.000Z",
    step_id: "step-search",
    step_label: "在闲鱼搜索「露营椅」",
  },
  {
    id: "xy-1002",
    title: "折叠月亮椅 带收纳袋",
    price: "¥65",
    platform: "xianyu",
    seller: "周末出摊",
    location: "上海",
    want_count: "8",
    product_url: "https://www.goofish.com/item?id=xy-1002",
    crawled_at: "2026-09-08T01:00:00.000Z",
    step_id: "step-search",
    step_label: "在闲鱼搜索「露营椅」",
  },
];

/** Demo：一份已完成的工作快照（不跑爬虫时可用于预览 UI）。 */
export function buildMockWorkDetail(workId = "mock-work-xhs"): AgentWorkDetailView {
  const products = MOCK_XHS_PRODUCTS;
  return {
    work_id: workId,
    title: "测试",
    status: status("ready", "已完成", "bg-emerald-500/15 text-emerald-600", "爬取直播结束"),
    messages: [
      {
        id: "msg-user",
        role: "user",
        content: "小红书 测试",
        created_at: "2026-09-08T01:00:00.000Z",
      },
      {
        id: "msg-assistant",
        role: "assistant",
        content: `已在小红书搜到 **${products.length}** 条与「测试」相关的结果。`,
        created_at: "2026-09-08T01:00:05.000Z",
        thinking: "用户想在小红书找「测试」。我会打开真实浏览器搜品并直播页面，再抽样看详情。",
        thinking_duration_sec: 4,
        steps: [
          {
            id: "step-search",
            kind: "browser_crawl",
            label: "在小红书搜索「测试」",
            hint: `抓到 ${products.length} 条`,
            status: status("ready", "已完成", "bg-emerald-500/15 text-emerald-600"),
            page: {
              url: "https://www.xiaohongshu.com/search_result?keyword=%E6%B5%8B%E8%AF%95",
              title: "小红书 · 测试",
              focus_label: `${products.length} 条结果`,
              loading: false,
            },
          },
          {
            id: "step-detail",
            kind: "product_sample",
            label: "抽样看详情",
            hint: "已核对价格与互动",
            status: status("ready", "已完成", "bg-emerald-500/15 text-emerald-600"),
          },
        ],
      },
    ],
    products: {
      items: products,
      total: products.length,
      status: status("ready", "已采集", "bg-emerald-500/15 text-emerald-600", `共 ${products.length} 条`),
    },
    recommendations: {
      items: [],
      total: 0,
      status: status("idle", "待生成", "bg-muted text-muted-foreground"),
      summary: null,
    },
    browser_live: {
      frame_id: null,
      url: "about:blank",
      title: "等待任务",
      status: status("idle", "待命", "bg-muted text-muted-foreground"),
      progress_hint: null,
      focus_label: null,
    },
    browser_history: [],
    composer_placeholder: "补充筛选条件或修改任务…",
    can_send: true,
    composer_agents: [],
    composer_agent_id: null,
    composer_model_id: null,
  };
}
