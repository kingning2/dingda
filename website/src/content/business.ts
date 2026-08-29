/** 与桌面端 `workspace-features.ts` 对齐的业务导航与演示数据。 */

export const WORKSPACE_NAV = [
  {
    label: "选品业务",
    items: [
      {
        title: "工作台",
        url: "/console",
        children: [{ title: "总览", url: "/console" }],
      },
      {
        title: "选品发现",
        children: [
          { title: "高利润机会", url: "/console/discovery/high-profit" },
          { title: "热门机会", url: "/console/discovery/hot" },
          { title: "蓝海机会", url: "/console/discovery/blue-ocean" },
          { title: "新发现", url: "/console/discovery/new" },
          { title: "开始选品", url: "/console/discovery/start" },
        ],
      },
      { title: "商品库", url: "/console/products" },
      {
        title: "利润分析",
        children: [
          { title: "利润计算器", url: "/console/profit/calculator" },
          { title: "成本模板", url: "/console/profit/templates" },
        ],
      },
      {
        title: "价格 / 竞品监控",
        children: [
          { title: "监控订阅", url: "/console/monitoring/subscriptions" },
          { title: "告警记录", url: "/console/monitoring/alerts" },
          { title: "规则配置", url: "/console/monitoring/rules" },
        ],
      },
      { title: "任务中心", url: "/console/tasks" },
    ],
  },
  {
    label: "系统",
    items: [
      {
        title: "设置",
        children: [
          { title: "通用", url: "/console/settings/general" },
          { title: "账号", url: "/console/settings/accounts" },
          { title: "采集", url: "/console/settings/collection" },
          { title: "利润默认", url: "/console/settings/profit" },
          { title: "AI 模型", url: "/console/settings/ai" },
        ],
      },
      { title: "官网首页", url: "/" },
    ],
  },
] as const;

/** 对齐桌面端 `DashboardStats` + 选品语义。 */
export const MOCK_STATS = [
  { label: "绑定账号", value: "5", hint: "活跃 4 个", trend: "up" as const },
  { label: "商品库", value: "128", hint: "本周 +12", trend: "up" as const },
  { label: "今日机会", value: "23", hint: "Agent 探索产出", trend: "up" as const },
  { label: "运行中任务", value: "2", hint: "比价探索进行中", trend: "up" as const },
];

export const OPPORTUNITY_COLUMNS = [
  { key: "title", header: "商品" },
  { key: "supplyPrice", header: "1688 采购价" },
  { key: "demandPrice", header: "闲鱼售价" },
  { key: "profit", header: "预计利润" },
  { key: "margin", header: "利润率" },
  { key: "competition", header: "竞争度" },
  { key: "score", header: "机会评分" },
] as const;

export const PRODUCT_COLUMNS = [
  { key: "title", header: "商品" },
  { key: "category", header: "类目" },
  { key: "supplyMin", header: "1688 最低价" },
  { key: "supplierCount", header: "供应商数" },
  { key: "demandPrice", header: "闲鱼市场价" },
  { key: "listingCount", header: "闲鱼商品数" },
  { key: "profit", header: "预计利润" },
  { key: "margin", header: "利润率" },
  { key: "competition", header: "竞争度" },
  { key: "score", header: "机会评分" },
  { key: "updatedAt", header: "更新时间" },
] as const;

export const TASK_COLUMNS = [
  { key: "id", header: "任务 ID" },
  { key: "type", header: "类型" },
  { key: "status", header: "状态" },
  { key: "progress", header: "进度" },
  { key: "updatedAt", header: "更新时间" },
] as const;

export type OpportunityRow = {
  title: string;
  supplyPrice: string;
  demandPrice: string;
  profit: string;
  margin: string;
  competition: string;
  score: string;
};

export type ProductRow = {
  title: string;
  category: string;
  supplyMin: string;
  supplierCount: string;
  demandPrice: string;
  listingCount: string;
  profit: string;
  margin: string;
  competition: string;
  score: string;
  updatedAt: string;
};

export type TaskRow = {
  id: string;
  type: string;
  status: string;
  progress: string;
  updatedAt: string;
};

export const MOCK_OPPORTUNITIES: OpportunityRow[] = [
  {
    title: "磁吸手机支架 · 车载款",
    supplyPrice: "¥12.8",
    demandPrice: "¥39.9",
    profit: "¥18.6",
    margin: "46.6%",
    competition: "中",
    score: "92",
  },
  {
    title: "桌面收纳盒 · 三层抽屉",
    supplyPrice: "¥23.5",
    demandPrice: "¥68.0",
    profit: "¥28.4",
    margin: "41.8%",
    competition: "低",
    score: "88",
  },
  {
    title: "Type-C 快充线 · 1.5m",
    supplyPrice: "¥6.2",
    demandPrice: "¥19.9",
    profit: "¥9.1",
    margin: "45.7%",
    competition: "高",
    score: "76",
  },
  {
    title: "硅胶锅铲套装 · 5 件",
    supplyPrice: "¥18.0",
    demandPrice: "¥49.9",
    profit: "¥21.3",
    margin: "42.7%",
    competition: "中",
    score: "84",
  },
];

export const MOCK_PRODUCTS: ProductRow[] = [
  {
    title: "磁吸手机支架 · 车载款",
    category: "3C 配件",
    supplyMin: "¥12.8",
    supplierCount: "126",
    demandPrice: "¥39.9",
    listingCount: "2.4k",
    profit: "¥18.6",
    margin: "46.6%",
    competition: "中",
    score: "92",
    updatedAt: "今天 09:12",
  },
  {
    title: "桌面收纳盒 · 三层抽屉",
    category: "家居收纳",
    supplyMin: "¥23.5",
    supplierCount: "89",
    demandPrice: "¥68.0",
    listingCount: "860",
    profit: "¥28.4",
    margin: "41.8%",
    competition: "低",
    score: "88",
    updatedAt: "昨天 18:40",
  },
  {
    title: "便携榨汁杯 · 350ml",
    category: "小家电",
    supplyMin: "¥31.0",
    supplierCount: "54",
    demandPrice: "¥89.0",
    listingCount: "1.1k",
    profit: "¥35.2",
    margin: "39.6%",
    competition: "中",
    score: "81",
    updatedAt: "昨天 11:05",
  },
];

export const MOCK_TASKS: TaskRow[] = [
  {
    id: "run-8f2a",
    type: "Agent 比价探索",
    status: "运行中",
    progress: "采集 12 / 20 · 配对分析中",
    updatedAt: "今天 15:02",
  },
  {
    id: "run-7c19",
    type: "热门品类扫描",
    status: "已完成",
    progress: "发现 8 个高利润机会",
    updatedAt: "今天 10:18",
  },
  {
    id: "run-6b04",
    type: "新手选品（不知道卖什么）",
    status: "排队中",
    progress: "Agent 规划关键词",
    updatedAt: "今天 09:55",
  },
];

export const DASHBOARD_SECTIONS = [
  { title: "今日商品机会", description: "今天最值得关注的选品机会。" },
  { title: "高利润商品", description: "按利润与利润率排序的机会。" },
  { title: "新发现商品", description: "最近采集、尚未充分分析。" },
  { title: "利润率上升", description: "利润变好的商品。" },
  { title: "竞争下降", description: "竞争变弱的商品。" },
  { title: "监控提醒", description: "价格 / 竞品 / 利润告警。" },
  { title: "最近任务", description: "Agent 比价探索、热门扫描等任务进度。" },
] as const;
