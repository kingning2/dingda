import type {
  AgentBrowserFrameView,
  AgentBrowserLiveView,
  AgentWorkDetailView,
  AgentWorkProductItem,
  AgentWorkProductsView,
  AgentWorkRecommendationItem,
  AgentWorkRecommendationsView,
  AgentWorkSendRequest,
  AgentWorkStatusView,
  AgentWorkStepView,
} from "@/contracts/ai-work";
import type { ComposerSubmitPayload } from "@/contracts/composer";
import type { CrawlProductItem } from "@/contracts/crawler";
import { getComposerAgentOptions, resolveDefaultAgentId } from "@/components/composer/composer-agents";
import { mockBrowserScreenshot } from "./mock-screenshots";
import { takeWorkDraft } from "./work-draft";

function mockComposerFields(agentId?: string | null, modelId?: string | null) {
  const agents = getComposerAgentOptions();
  return {
    composer_agents: agents,
    composer_agent_id: agentId ?? resolveDefaultAgentId(agents),
    composer_model_id: modelId ?? null,
  };
}

function status(
  state: string,
  label: string,
  badge_class: string,
  hint?: string | null,
): AgentWorkStatusView {
  return { state, label, badge_class, hint };
}

function idleLive(): AgentBrowserLiveView {
  return {
    frame_id: null,
    url: "about:blank",
    title: "等待任务",
    status: status("idle", "待命", "bg-muted text-muted-foreground"),
    progress_hint: "Agent 开始执行后，这里会同步当前浏览的网页。",
    focus_label: null,
  };
}

function emptyProducts(hint?: string | null): AgentWorkProductsView {
  return {
    items: [],
    total: 0,
    status: status("idle", "等待抓取", "bg-muted text-muted-foreground", hint ?? "抓取到的商品会显示在对话步骤下"),
  };
}

function emptyRecommendations(hint?: string | null): AgentWorkRecommendationsView {
  return {
    items: [],
    total: 0,
    status: status("idle", "待生成", "bg-muted text-muted-foreground", hint ?? "任务完成后展示推荐结果与依据"),
    summary: null,
  };
}

const RECOMMENDATION_META: Array<{ reason: string; basis: string }> = [
  {
    reason: "售价低于预算上限，同款全新价约 ¥220，性价比突出。",
    basis: "预算 ¥200 · 当前售价 ¥168 · 闲鱼同款均价 ¥195",
  },
  {
    reason: "轻便易携带，适合周末露营，卖家信用良好。",
    basis: "重量约 1.2kg · 卖家好评率 98% · 近 30 天成交 42 单",
  },
  {
    reason: "两把装均价更低，适合家庭出行，配件齐全。",
    basis: "套装单价 ¥64/把 · 含收纳袋 · 评价提及「结实耐用」",
  },
  {
    reason: "铝合金支架耐用，承重高，长期使用成本更低。",
    basis: "承重 300 斤 · 材质铝合金 · 使用痕迹轻微",
  },
];

function mockRecommendationsFromProducts(
  items: AgentWorkProductItem[],
  summary: string,
): AgentWorkRecommendationsView {
  const recommended = items.slice(0, 4).map((item, index) => {
    const meta = RECOMMENDATION_META[index] ?? RECOMMENDATION_META[0];
    return {
      ...item,
      recommendation_reason: meta.reason,
      recommendation_basis: meta.basis,
    } satisfies AgentWorkRecommendationItem;
  });

  return {
    items: recommended,
    total: recommended.length,
    status: status("success", "已生成", "bg-emerald-500/15 text-emerald-600", "基于抓取数据与预算条件筛选"),
    summary,
  };
}

function productsSnapshot(
  items: AgentWorkProductItem[],
  label: string,
  hint?: string | null,
  state = "running",
): AgentWorkProductsView {
  return {
    items,
    total: items.length,
    status: status(state, label, state === "success" ? "bg-emerald-500/15 text-emerald-600" : "bg-sky-500/15 text-sky-600", hint),
  };
}

const MOCK_CAMPING_PRODUCTS: CrawlProductItem[] = [
  {
    id: "camp-1",
    title: "牧高笛露营椅 承重 300 斤 可折叠",
    price: "¥168",
    platform: "xianyu",
    seller: "户外装备铺",
    location: "上海",
    crawled_at: "2026-09-01T09:10:40+08:00",
  },
  {
    id: "camp-2",
    title: "黑鹿月亮椅 轻便便携",
    price: "¥89",
    platform: "xianyu",
    seller: "露营爱好者",
    location: "杭州",
    crawled_at: "2026-09-01T09:10:42+08:00",
  },
  {
    id: "camp-3",
    title: "原始人折叠椅 两把装",
    price: "¥128",
    platform: "xianyu",
    seller: "野营小店",
    location: "广州",
    crawled_at: "2026-09-01T09:10:44+08:00",
  },
  {
    id: "camp-4",
    title: "挪客超轻露营椅 铝合金",
    price: "¥195",
    platform: "xianyu",
    seller: "户外折扣仓",
    location: "北京",
    crawled_at: "2026-09-01T09:10:50+08:00",
  },
  {
    id: "camp-5",
    title: "迪卡侬露营椅 九成新",
    price: "¥75",
    platform: "xianyu",
    seller: "二手户外",
    location: "深圳",
    crawled_at: "2026-09-01T09:10:52+08:00",
  },
  {
    id: "camp-6",
    title: "探险者月亮椅 带杯托",
    price: "¥58",
    platform: "xianyu",
    seller: "平价露营",
    location: "成都",
    crawled_at: "2026-09-01T09:10:55+08:00",
  },
];

function mockProductsForQuery(
  query: string,
  count: number,
  stepId: string,
  stepLabel: string,
): AgentWorkProductItem[] {
  const keyword = query.trim() || "商品";
  const pool = MOCK_CAMPING_PRODUCTS.map((item, index) => ({
    ...item,
    id: `${stepId}-${index + 1}-${Date.now()}`,
    title: keyword.includes("露营") ? item.title : `${keyword} · ${item.title.split(" ").slice(-2).join(" ")}`,
    crawled_at: new Date().toISOString(),
    step_id: stepId,
    step_label: stepLabel,
  }));
  return pool.slice(0, count);
}

function tagCampingProducts(
  items: CrawlProductItem[],
  stepId: string,
  stepLabel: string,
): AgentWorkProductItem[] {
  return items.map((item) => ({
    ...item,
    step_id: stepId,
    step_label: stepLabel,
  }));
}

function mockTitleFromPrompt(prompt: string): string {
  const trimmed = prompt.trim();
  if (!trimmed) return "AI 选品任务";
  return trimmed.length > 24 ? `${trimmed.slice(0, 24)}…` : trimmed;
}

function withScreenshot(live: AgentBrowserLiveView): AgentBrowserLiveView {
  if (live.screenshot_url || live.url === "about:blank") return live;
  return {
    ...live,
    screenshot_url: mockBrowserScreenshot(live.title, live.focus_label),
  };
}

function archiveLiveFrame(
  live: AgentBrowserLiveView,
  label: string,
  history: AgentBrowserFrameView[],
): AgentBrowserFrameView[] {
  if (live.url === "about:blank") return history;

  const settled = withScreenshot(live);
  const frame: AgentBrowserFrameView = {
    id: settled.frame_id ?? `frame-${history.length + 1}`,
    url: settled.url,
    title: settled.title,
    focus_label: settled.focus_label,
    screenshot_url: settled.screenshot_url!,
    captured_at: new Date().toISOString(),
    label,
  };

  return [...history, frame];
}

function buildInitialDetail(
  workId: string,
  seed?: Pick<ComposerSubmitPayload, "message" | "agent_id" | "model_id"> | null,
): AgentWorkDetailView {
  const seedPrompt = seed?.message ?? null;
  const title = seedPrompt ? mockTitleFromPrompt(seedPrompt) : "新任务";
  const composer = mockComposerFields(seed?.agent_id, seed?.model_id);
  return {
    work_id: workId,
    title,
    status: seedPrompt
      ? status("ready", "就绪", "bg-muted text-muted-foreground", "正在启动任务…")
      : status("ready", "就绪", "bg-muted text-muted-foreground", "输入需求后开始执行"),
    messages: [],
    products: emptyProducts(),
    recommendations: emptyRecommendations(),
    browser_live: idleLive(),
    browser_history: [],
    composer_placeholder: "补充筛选条件或修改任务…",
    can_send: !seedPrompt,
    ...composer,
  };
}

/** 营销 demo 工作 id（非 createWorkId 的 work-*）。留给后续 demo 页使用。 */
export function isDemoWorkId(workId: string): boolean {
  return !workId.startsWith("work-");
}

/** 营销演示：露营椅选品完整快照（仅 mock，不写 SQLite）。 */
function buildDemoDetail(workId: string): AgentWorkDetailView {
  const composer = mockComposerFields();
  const homeFrameId = `${workId}-frame-home`;
  const loginFrameId = `${workId}-frame-login`;

  return {
    work_id: workId,
    title: "露营椅选品分析",
    status: status("ready", "就绪", "bg-muted text-muted-foreground", "输入需求后开始执行"),
    messages: [
      {
        id: `${workId}-user-0`,
        role: "user",
        content: "帮我在闲鱼找性价比高的露营椅，预算 200 以内，整理成对比表。",
        created_at: "2026-09-01T09:10:00+08:00",
      },
      {
        id: `${workId}-assistant-0`,
        role: "assistant",
        content: "好的，我会先在闲鱼搜索露营椅，再筛选符合预算的商品并整理对比。",
        created_at: "2026-09-01T09:10:08+08:00",
        steps: [
          {
            id: "step-login",
            label: "检查闲鱼账号登录态",
            status: status("success", "已完成", "bg-emerald-500/15 text-emerald-600"),
            browser_frame_id: loginFrameId,
          },
          {
            id: "step-search",
            label: "搜索关键词「露营椅」",
            status: status("running", "进行中", "bg-sky-500/15 text-sky-600", "正在翻页抓取…"),
            browser_frame_id: `${workId}-frame-search`,
          },
          {
            id: "step-filter",
            label: "按预算筛选并去重",
            status: status("pending", "等待中", "bg-muted text-muted-foreground"),
          },
        ],
      },
    ],
    products: productsSnapshot(
      tagCampingProducts(MOCK_CAMPING_PRODUCTS.slice(0, 4), "step-search", "搜索关键词「露营椅」"),
      "抓取中",
      "已抓取 4 条，继续翻页…",
    ),
    recommendations: mockRecommendationsFromProducts(
      tagCampingProducts(MOCK_CAMPING_PRODUCTS.slice(0, 4), "step-search", "搜索关键词「露营椅」"),
      "在预算 ¥200 内，综合价格、成色与卖家信誉，优先推荐以下 4 款露营椅。",
    ),
    browser_history: [
      {
        id: homeFrameId,
        url: "https://www.goofish.com/",
        title: "闲鱼",
        focus_label: "首页",
        screenshot_url: mockBrowserScreenshot("闲鱼", "首页"),
        captured_at: "2026-09-01T09:10:12+08:00",
        label: "打开闲鱼首页",
      },
      {
        id: loginFrameId,
        url: "https://www.goofish.com/login",
        title: "闲鱼 - 登录",
        focus_label: "登录页",
        screenshot_url: mockBrowserScreenshot("闲鱼 - 登录", "登录页"),
        captured_at: "2026-09-01T09:10:20+08:00",
        label: "校验账号登录态",
      },
      {
        id: `${workId}-frame-search`,
        url: "https://www.goofish.com/search?q=%E9%9C%B2%E8%90%A5%E6%A4%85",
        title: "闲鱼 - 露营椅 搜索结果",
        focus_label: "搜索结果列表",
        screenshot_url: mockBrowserScreenshot("闲鱼 - 露营椅 搜索结果", "搜索结果列表"),
        captured_at: "2026-09-01T09:10:35+08:00",
        label: "搜索露营椅",
      },
    ],
    browser_live: withScreenshot({
      frame_id: `${workId}-frame-page2`,
      url: "https://www.goofish.com/search?q=%E9%9C%B2%E8%90%A5%E6%A4%85&page=2",
      title: "闲鱼 - 露营椅 第 2 页",
      status: status("running", "浏览中", "bg-sky-500/15 text-sky-600", "正在加载第 2 页"),
      progress_hint: "Agent 正在翻页查看商品列表",
      focus_label: "第 2 页列表",
    }),
    composer_placeholder: "补充筛选条件或修改任务…",
    can_send: true,
    ...composer,
  };
}

function cloneWorkDetail(detail: AgentWorkDetailView): AgentWorkDetailView {
  return {
    ...detail,
    status: { ...detail.status },
    messages: detail.messages.map((message) => ({
      ...message,
      steps: message.steps?.map((step) => ({ ...step, status: { ...step.status } })),
      attachments: message.attachments?.map((attachment) => ({ ...attachment })),
    })),
    products: {
      ...detail.products,
      status: { ...detail.products.status },
      items: detail.products.items.map((item) => ({ ...item })),
    },
    recommendations: {
      ...detail.recommendations,
      status: { ...detail.recommendations.status },
      items: detail.recommendations.items.map((item) => ({ ...item })),
    },
    browser_live: {
      ...detail.browser_live,
      status: { ...detail.browser_live.status },
    },
    browser_history: detail.browser_history.map((frame) => ({ ...frame })),
    composer_agents: detail.composer_agents.map((agent) => ({ ...agent })),
  };
}

const detailCache = new Map<string, AgentWorkDetailView>();

type InflightLoad = {
  promise: Promise<AgentWorkDetailLoadResult>;
  listeners: Set<(detail: AgentWorkDetailView) => void>;
};

const inflightLoads = new Map<string, InflightLoad>();

function isSettledDetail(detail: AgentWorkDetailView): boolean {
  return detail.can_send;
}

function notifyListeners(workId: string, detail: AgentWorkDetailView, extra?: (detail: AgentWorkDetailView) => void) {
  detailCache.set(workId, detail);
  const snapshot = cloneWorkDetail(detail);
  extra?.(snapshot);
  inflightLoads.get(workId)?.listeners.forEach((listener) => listener(snapshot));
}

export interface AgentWorkDetailLoadResult {
  detail: AgentWorkDetailView;
  /** 来自首页草稿、尚未发送的首条消息（仅 autoSend=false 时返回）。 */
  pendingSend: ComposerSubmitPayload | null;
}

export interface MockFetchAgentWorkDetailOptions {
  /** 为 false 时仅构建初始详情，不自动 mock 发送。默认 true。 */
  autoSend?: boolean;
}

function hydrateComposerAgents(detail: AgentWorkDetailView): AgentWorkDetailView {
  const agents = getComposerAgentOptions();
  return {
    ...detail,
    composer_agents: agents,
    composer_agent_id:
      detail.composer_agent_id && agents.some((agent) => agent.id === detail.composer_agent_id)
        ? detail.composer_agent_id
        : resolveDefaultAgentId(agents),
  };
}

/**
 * 营销 demo 加载（仅内存 mock）。
 * 真实工作页请用 ``loadAgentWorkDetail``，不要引用本函数。
 */
export async function mockFetchAgentWorkDetail(
  workId: string,
  onUpdate?: (detail: AgentWorkDetailView) => void,
  options?: MockFetchAgentWorkDetailOptions,
): Promise<AgentWorkDetailLoadResult> {
  const cached = detailCache.get(workId);
  if (cached && isSettledDetail(cached)) {
    const detail = hydrateComposerAgents(cloneWorkDetail(cached));
    onUpdate?.(detail);
    return { detail, pendingSend: null };
  }

  const existing = inflightLoads.get(workId);
  if (existing) {
    if (onUpdate) {
      if (cached) onUpdate(hydrateComposerAgents(cloneWorkDetail(cached)));
      existing.listeners.add(onUpdate);
    }
    return existing.promise;
  }

  const listeners = new Set<(detail: AgentWorkDetailView) => void>();
  if (onUpdate) listeners.add(onUpdate);

  const promise = (async (): Promise<AgentWorkDetailLoadResult> => {
    const seedDraft = takeWorkDraft(workId);

    if (!seedDraft && cached) {
      const detail = hydrateComposerAgents(cloneWorkDetail(cached));
      listeners.forEach((listener) => listener(detail));
      return { detail, pendingSend: null };
    }

    const detail = seedDraft
      ? buildInitialDetail(workId, seedDraft)
      : buildDemoDetail(workId);
    detailCache.set(workId, detail);
    listeners.forEach((listener) => listener(cloneWorkDetail(detail)));

    if (seedDraft?.message.trim()) {
      if (options?.autoSend === false) {
        const clone = cloneWorkDetail(detail);
        return { detail: clone, pendingSend: seedDraft };
      }

      const sent = await mockAgentWorkSend({
        work_id: workId,
        message: seedDraft.message,
        agent_id: seedDraft.agent_id,
        attachments: seedDraft.attachments,
      });
      return { detail: sent, pendingSend: null };
    }

    return { detail: cloneWorkDetail(detail), pendingSend: null };
  })();

  inflightLoads.set(workId, { promise, listeners });
  try {
    return await promise;
  } finally {
    inflightLoads.delete(workId);
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function withMessageField(
  detail: AgentWorkDetailView,
  messageId: string,
  field: "content" | "thinking",
  value: string,
): AgentWorkDetailView {
  return {
    ...detail,
    messages: detail.messages.map((message) =>
      message.id === messageId ? { ...message, [field]: value } : message,
    ),
  };
}

/** 模拟 SSE/流式字段：按字符逐步推送快照。 */
async function streamMessageField(
  workId: string,
  detail: AgentWorkDetailView,
  messageId: string,
  field: "content" | "thinking",
  targetContent: string,
  onUpdate?: (detail: AgentWorkDetailView) => void,
  options?: { charMs?: number; charsPerTick?: number },
): Promise<AgentWorkDetailView> {
  const charMs = options?.charMs ?? 10;
  const charsPerTick = options?.charsPerTick ?? 6;
  const current =
    detail.messages.find((message) => message.id === messageId)?.[field] ?? "";
  const startAt = current.length;

  if (targetContent.length <= startAt) {
    if (startAt > targetContent.length) {
      return detail;
    }
    return pushUpdate(workId, withMessageField(detail, messageId, field, targetContent), onUpdate);
  }

  let snapshot = detail;
  let pos = startAt;
  while (pos < targetContent.length) {
    pos = Math.min(pos + charsPerTick, targetContent.length);
    const value = targetContent.slice(0, pos);
    snapshot = withMessageField(snapshot, messageId, field, value);
    pushUpdate(workId, snapshot, onUpdate);
    if (pos >= targetContent.length) break;
    await delay(charMs);
  }

  return snapshot;
}

/** 模拟 SSE/流式正文：按字符逐步推送快照。 */
async function streamMessageContent(
  workId: string,
  detail: AgentWorkDetailView,
  messageId: string,
  targetContent: string,
  onUpdate?: (detail: AgentWorkDetailView) => void,
  options?: { charMs?: number; charsPerTick?: number },
): Promise<AgentWorkDetailView> {
  return streamMessageField(workId, detail, messageId, "content", targetContent, onUpdate, options);
}

function appendProduct(
  detail: AgentWorkDetailView,
  product: AgentWorkProductItem,
  label = "抓取中",
): AgentWorkDetailView {
  const items = [...detail.products.items, product];
  return {
    ...detail,
    products: productsSnapshot(
      items,
      label,
      `已发现 ${items.length} 条商品，继续检索…`,
      items.length > 0 ? "running" : "idle",
    ),
  };
}

/** 爬虫阶段逐条推送商品（不写入 thinking，由步骤卡片展示）。 */
async function discoverProductsIncrementally(
  workId: string,
  detail: AgentWorkDetailView,
  products: AgentWorkProductItem[],
  onUpdate?: (detail: AgentWorkDetailView) => void,
  options?: { itemMs?: number },
): Promise<AgentWorkDetailView> {
  const itemMs = options?.itemMs ?? 360;
  let snapshot = detail;

  for (const product of products) {
    snapshot = appendProduct(snapshot, product);
    pushUpdate(workId, snapshot, onUpdate);
    await delay(itemMs);
  }

  return snapshot;
}

function withAssistantSteps(
  detail: AgentWorkDetailView,
  messageId: string,
  steps: AgentWorkStepView[],
): AgentWorkDetailView {
  return {
    ...detail,
    messages: detail.messages.map((message) =>
      message.id === messageId ? { ...message, steps } : message,
    ),
  };
}

function mapAssistantSteps(
  detail: AgentWorkDetailView,
  messageId: string,
  mapper: (steps: AgentWorkStepView[]) => AgentWorkStepView[],
): AgentWorkDetailView {
  const message = detail.messages.find((item) => item.id === messageId);
  if (!message) return detail;
  return withAssistantSteps(detail, messageId, mapper(message.steps ?? []));
}

function pushUpdate(
  workId: string,
  next: AgentWorkDetailView,
  onUpdate?: (detail: AgentWorkDetailView) => void,
): AgentWorkDetailView {
  notifyListeners(workId, next, onUpdate);
  return next;
}

function nextFrameId(workId: string, step: string): string {
  return `${workId}-frame-${step}-${Date.now()}`;
}

/**
 * 模拟 agent_work_send API：推送若干完整快照（轮询 / SSE 时同理）。
 */
export async function mockAgentWorkSend(
  request: AgentWorkSendRequest,
  onUpdate?: (detail: AgentWorkDetailView) => void,
): Promise<AgentWorkDetailView> {
  const { work_id: workId, message, agent_id, model_id, attachments = [] } = request;
  const base = detailCache.get(workId) ?? buildInitialDetail(workId);
  const userMessage = {
    id: `${workId}-user-${Date.now()}`,
    role: "user" as const,
    content: message.trim(),
    created_at: new Date().toISOString(),
    ...(attachments.length > 0 ? { attachments } : {}),
  };

  const homeFrameId = nextFrameId(workId, "home");
  let history = base.browser_history;
  let live: AgentBrowserLiveView = {
    frame_id: homeFrameId,
    url: "https://www.goofish.com/",
    title: "闲鱼",
    status: status("running", "浏览中", "bg-sky-500/15 text-sky-600", "正在打开首页"),
    progress_hint: "Agent 正在打开闲鱼",
    focus_label: "首页",
  };

  let snapshot: AgentWorkDetailView = {
    ...base,
    title: mockTitleFromPrompt(message) || base.title,
    status: status("running", "执行中", "bg-sky-500/15 text-sky-600", "Agent 正在编排任务"),
    messages: [...base.messages, userMessage],
    can_send: false,
    composer_agent_id: agent_id ?? base.composer_agent_id,
    composer_model_id: model_id ?? base.composer_model_id ?? null,
    products: emptyProducts("正在打开目标平台…"),
    recommendations: emptyRecommendations(),
    browser_history: history,
    browser_live: live,
  };
  pushUpdate(workId, snapshot, onUpdate);
  await delay(700);

  history = archiveLiveFrame(live, "打开闲鱼首页", history);
  const loginFrameId = nextFrameId(workId, "login");
  live = {
    frame_id: loginFrameId,
    url: "https://www.goofish.com/login",
    title: "闲鱼 - 登录",
    status: status("running", "浏览中", "bg-amber-500/15 text-amber-700", "校验登录态"),
    progress_hint: "使用已绑定账号登录",
    focus_label: "登录页",
    screenshot_url: mockBrowserScreenshot("闲鱼 - 登录", "登录页"),
  };

  const assistantId = `${workId}-assistant-${Date.now()}`;
  const searchLabel = `搜索「${message.trim().slice(0, 12)}」`;
  const collectLabel = "抓取商品并整理对比";
  const thinkingRound1 = "分析任务：需要在闲鱼检索相关商品，核对预算与成色，先确认登录态再开始检索。";
  const thinkingRound2 = `${thinkingRound1}\n\n第 1 页检索完成，对比价格与成色，继续翻第 2 页补充候选。`;
  const thinkingRound3 = `${thinkingRound2}\n\n候选已足够，没有更多页面需要抓取，开始整理结论。`;

  snapshot = {
    ...snapshot,
    messages: [
      ...snapshot.messages,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        thinking: "",
        created_at: new Date().toISOString(),
      },
    ],
    products: emptyProducts("思考完成后开始抓取"),
    recommendations: emptyRecommendations(),
    browser_history: history,
    browser_live: live,
  };
  pushUpdate(workId, snapshot, onUpdate);

  // ① 思考
  snapshot = await streamMessageField(
    workId,
    snapshot,
    assistantId,
    "thinking",
    thinkingRound1,
    onUpdate,
    { charMs: 10, charsPerTick: 6 },
  );

  // ② 爬虫：登录 + 搜索第 1 页
  history = archiveLiveFrame(live, "校验账号登录态", history);
  const searchFrameId = nextFrameId(workId, "search");
  live = {
    frame_id: searchFrameId,
    url: `https://www.goofish.com/search?q=${encodeURIComponent(message.trim())}`,
    title: `闲鱼 - ${message.trim()} 搜索结果`,
    status: status("running", "浏览中", "bg-sky-500/15 text-sky-600", "正在加载列表"),
    progress_hint: "Agent 正在查看搜索结果",
    focus_label: "搜索结果列表",
    screenshot_url: mockBrowserScreenshot(`闲鱼 - ${message.trim()} 搜索结果`, "搜索结果列表"),
  };

  snapshot = withAssistantSteps(snapshot, assistantId, [
    {
      id: "step-login",
      label: "检查闲鱼账号登录态",
      status: status("success", "已完成", "bg-emerald-500/15 text-emerald-600"),
      browser_frame_id: history[history.length - 1]?.id ?? loginFrameId,
    },
    {
      id: "step-search",
      label: searchLabel,
      status: status("running", "进行中", "bg-sky-500/15 text-sky-600", "翻页抓取中"),
      browser_frame_id: searchFrameId,
    },
    {
      id: "step-collect",
      label: collectLabel,
      status: status("pending", "等待中", "bg-muted text-muted-foreground"),
    },
  ]);
  snapshot = { ...snapshot, browser_history: history, browser_live: live };
  pushUpdate(workId, snapshot, onUpdate);

  const searchProducts = mockProductsForQuery(message, 4, "step-search", searchLabel);
  snapshot = await discoverProductsIncrementally(workId, snapshot, searchProducts, onUpdate);

  // ③ 再思考
  snapshot = await streamMessageField(
    workId,
    snapshot,
    assistantId,
    "thinking",
    thinkingRound2,
    onUpdate,
    { charMs: 10, charsPerTick: 6 },
  );

  // ④ 爬虫：第 2 页补充抓取
  history = archiveLiveFrame(live, searchLabel, history);
  const page2FrameId = nextFrameId(workId, "page2");
  live = withScreenshot({
    frame_id: page2FrameId,
    url: `https://www.goofish.com/search?q=${encodeURIComponent(message.trim())}&page=2`,
    title: `闲鱼 - ${message.trim()} 第 2 页`,
    status: status("running", "浏览中", "bg-sky-500/15 text-sky-600", "继续翻页"),
    progress_hint: "Agent 正在查看第 2 页",
    focus_label: "第 2 页列表",
  });

  snapshot = mapAssistantSteps(snapshot, assistantId, (steps) =>
    steps.map((step) =>
      step.id === "step-search"
        ? {
            ...step,
            status: status("success", "已完成", "bg-emerald-500/15 text-emerald-600"),
            browser_frame_id: history[history.length - 1]?.id ?? searchFrameId,
          }
        : step.id === "step-collect"
          ? {
              ...step,
              status: status("running", "进行中", "bg-sky-500/15 text-sky-600", "补充抓取中"),
              browser_frame_id: page2FrameId,
            }
          : step,
    ),
  );
  snapshot = { ...snapshot, browser_history: history, browser_live: live };
  pushUpdate(workId, snapshot, onUpdate);

  const collectProducts = mockProductsForQuery(message, 2, "step-collect", collectLabel);
  snapshot = await discoverProductsIncrementally(workId, snapshot, collectProducts, onUpdate);

  // ⑤ 再思考（确认无更多抓取）
  snapshot = await streamMessageField(
    workId,
    snapshot,
    assistantId,
    "thinking",
    thinkingRound3,
    onUpdate,
    { charMs: 10, charsPerTick: 6 },
  );

  // ⑥ 输出结果
  const productTotal = snapshot.products.items.length;
  snapshot = mapAssistantSteps(snapshot, assistantId, (steps) =>
    steps.map((step) =>
      step.id === "step-collect"
        ? {
            ...step,
            status: status("success", "已完成", "bg-emerald-500/15 text-emerald-600"),
            browser_frame_id: page2FrameId,
          }
        : step,
    ),
  );
  snapshot = {
    ...snapshot,
    status: status("running", "执行中", "bg-sky-500/15 text-sky-600", "整理结果中"),
    products: {
      ...snapshot.products,
      total: productTotal,
      status: status("success", "已完成", "bg-emerald-500/15 text-emerald-600", `共入库 ${productTotal} 条商品`),
    },
    recommendations: mockRecommendationsFromProducts(
      snapshot.products.items,
      `结合你的需求「${message.trim().slice(0, 20)}」与预算条件，从 ${productTotal} 条抓取结果中筛选出最值得关注的款式。`,
    ),
    browser_live: withScreenshot({
      ...live,
      status: status("success", "停留中", "bg-emerald-500/15 text-emerald-600"),
      progress_hint: "Agent 当前停在第 2 页",
    }),
  };
  pushUpdate(workId, snapshot, onUpdate);

  const finalReply = `已发现 ${productTotal} 条符合预算的商品并完成对比。右侧可回看每一步的页面截图，推荐结果已整理在结果 Tab。`;
  snapshot = await streamMessageContent(
    workId,
    snapshot,
    assistantId,
    finalReply,
    onUpdate,
    { charMs: 8, charsPerTick: 8 },
  );

  snapshot = {
    ...snapshot,
    status: status("success", "已完成", "bg-emerald-500/15 text-emerald-600"),
    can_send: true,
  };

  return pushUpdate(workId, snapshot, onUpdate);
}
