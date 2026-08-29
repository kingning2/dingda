/**
 * 叮答产品定位 — 官网与控制台演示的叙事单一真相源。
 *
 * 对齐桌面端选品 L1；比价能力 = Agent 编排 + 渠道爬虫联合探索，非静态价表对比。
 */

export const PRODUCT_POSITIONING = {
  name: "叮答",
  tagline: "用 Agent 帮你探索最近火的货，找出有利润的品",
  subtitle:
    "不管是已经在闲鱼/1688 上跑的商家，还是刚想入门的小白，都能通过 Agent + 爬虫自动比价、发现机会、算清利润。",
  audience: ["正在做的卖家", "想入门的小白", "跨平台倒货/无货源"],
} as const;

/** Agent 比价流水线（与桌面端 price_compare 节点对齐）。 */
export const AGENT_PIPELINE = [
  { step: "规划", desc: "Agent 根据你的关键词或品类，规划搜索方向与比对策略" },
  { step: "采集", desc: "爬虫抓取 1688 供货端与闲鱼需求端的真实挂牌数据" },
  { step: "配对", desc: "同款归一、字段对齐，把两边商品拉到同一张表里" },
  { step: "分析", desc: "交叉核验价格、估算利润与竞争度，给出机会评分" },
] as const;

export const VALUE_PROPS = [
  {
    seal: "探",
    title: "Agent 探索比价",
    desc: "不是查一张价目表，而是 Agent 带着爬虫去市场里找——规划关键词、采集渠道、配对同款、算利润。",
  },
  {
    seal: "火",
    title: "盯最近火的货",
    desc: "高利润、热门、蓝海、新发现——按市场热度和利润空间筛出当下值得关注的品类与单品。",
  },
  {
    seal: "算",
    title: "利润一眼看清",
    desc: "1688 采购价、闲鱼售价、预计利润与利润率同台展示，不用自己扒数据、拉表格。",
  },
  {
    seal: "库",
    title: "机会沉淀成库",
    desc: "看好的品进入标准商品库，持续跟踪指标变化，而不是散落在聊天记录里。",
  },
  {
    seal: "盯",
    title: "变动持续监控",
    desc: "价格、竞品、利润告警——火过的货也会变，帮你盯住后续波动。",
  },
  {
    seal: "本",
    title: "数据留在本地",
    desc: "账号、采集结果、商品库存在本机，Rust 协调、Agent 只读查询，你掌控每一步操作。",
  },
] as const;

export const WORKFLOW_STEPS = [
  { title: "连接账号", desc: "绑定闲鱼与 1688，让爬虫能采到真实市场数据" },
  { title: "开始选品", desc: "输入商品名、品类，或让 Agent 帮你想卖什么" },
  { title: "Agent 探索", desc: "自动规划、采集、配对、分析，产出机会列表" },
  { title: "挑品入库", desc: "把有利润的货沉淀到商品库，持续跟踪" },
] as const;

export { FAQS } from "./faq";
