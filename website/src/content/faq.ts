/**
 * FAQ 内容 — 对齐 SpyX 三类结构 + SEO 向问答写法。
 * `answer` 为纯文本（JSON-LD / llms.txt）；`paragraphs` 用于页面展示。
 */

export type FaqLink = { label: string; href: string };

export type FaqItem = {
  id: string;
  title: string;
  answer: string;
  paragraphs: string[];
  links?: FaqLink[];
};

export type FaqCategoryId = "product" | "start" | "account";

export type FaqCategory = {
  id: FaqCategoryId;
  label: string;
  subtitle: string;
  seal: string;
  items: FaqItem[];
};

export const FAQ_CATEGORIES: FaqCategory[] = [
  {
    id: "product",
    label: "产品 FAQ",
    subtitle: "叮答是什么、怎么工作、安不安全",
    seal: "品",
    items: [
      {
        id: "how-it-works",
        title: "叮答是怎么工作的？",
        answer:
          "叮答是本地优先的闲鱼 × 1688 选品桌面工具。你绑定账号并发起选品后，Agent 会规划搜索方向，爬虫采集 1688 供货端与闲鱼需求端的真实挂牌，再配对同款、交叉核验价格，输出预计利润与竞争度。整个过程在任务中心可追踪。官网提供控制台演示，桌面端下载后可在本机运行完整流程。",
        paragraphs: [
          "叮答是本地优先的闲鱼 × 1688 选品桌面工具，核心不是查一张静态价表，而是用 Agent 带着爬虫去市场里探索。",
          "你绑定账号并发起选品后，Agent 规划搜索方向 → 爬虫采集双边挂牌 → 同款配对 → 利润与竞争度分析。任务进度可在任务中心查看。",
        ],
        links: [
          { label: "控制台演示", href: "/console/" },
          { label: "下载桌面端", href: "https://github.com/kingning2/dingda/releases" },
        ],
      },
      {
        id: "what-is",
        title: "叮答是什么？",
        answer:
          "叮答（DingDa）是开源的电商选品工具，帮商家和小白在闲鱼与 1688 之间自动探索最近比较火的货，并测算有没有利润空间。它把找热门、双边采集、算利润、沉淀商品库、持续监控串成一条工作流，数据默认保存在本机。",
        paragraphs: [
          "叮答（DingDa）是面向闲鱼 × 1688 的选品桌面应用：用 Agent + 爬虫发现机会，用利润测算帮你判断值不值得做。",
          "不管你是已经在跑的卖家，还是刚想入门的小白，都可以用同一套工具找品、算利润、把机会沉淀到商品库。",
        ],
        links: [{ label: "GitHub 源码", href: "https://github.com/kingning2/dingda" }],
      },
      {
        id: "is-free",
        title: "叮答是免费的吗？",
        answer:
          "叮答桌面端开源免费，可在 GitHub Releases 下载。你需要自行准备闲鱼/1688 账号与可选的 AI 模型 API Key（若使用云端大模型）。官网控制台演示无需安装，可直接预览界面与流程。",
        paragraphs: [
          "桌面端开源免费，在 GitHub Releases 下载安装即可使用核心选品能力。",
          "渠道账号需自行准备；若启用 Agent 推理，可按需在设置中配置 AI 模型（支持本地或云端）。",
        ],
        links: [
          { label: "免费下载", href: "https://github.com/kingning2/dingda/releases" },
          { label: "在线演示", href: "/console/" },
        ],
      },
      {
        id: "is-real",
        title: "叮答靠谱吗？真的能用吗？",
        answer:
          "叮答是真实在开发的开源项目，桌面端已具备选品发现、Agent 比价探索、商品库、利润分析与任务中心等模块。官网控制台为对齐桌面端的演示骨架；完整采集与比价需在桌面端连接真实账号后运行。",
        paragraphs: [
          "这是正在积极迭代的开源项目，核心模块与桌面端 L1 导航一一对齐。",
          "官网控制台让你先熟悉界面；真实 Agent 探索与爬虫采集需在桌面端绑定闲鱼/1688 后执行。",
        ],
        links: [
          { label: "查看演示", href: "/console/" },
          { label: "项目仓库", href: "https://github.com/kingning2/dingda" },
        ],
      },
      {
        id: "is-safe",
        title: "叮答安全吗？数据会上传云端吗？",
        answer:
          "叮答采用本地优先架构：账号、采集结果、商品库默认存在本机 SQLite，由 Rust 层读写。Agent 通过只读接口查询数据，不会自动替你上架、发消息或下单。关键操作需你在桌面端确认。",
        paragraphs: [
          "数据默认留在你的电脑上，不上传到叮答的云端服务器。",
          "Agent 只读查询本地数据，不会自动执行上架、发消息等敏感操作。",
        ],
      },
      {
        id: "price-compare",
        title: "「比价」和传统查价工具有什么不同？",
        answer:
          "传统查价多是静态关键词搜一下价格。叮答的比价是 Agent 编排的探索任务：规划方向、爬虫采集 1688 与闲鱼真实挂牌、同款归一、交叉核验后给出利润与竞争度评分，适合找最近火的、有利润空间的货，而不是只看某一个固定 SKU。",
        paragraphs: [
          "查价器回答「这个品现在多少钱」；叮答回答「最近什么火、同款两边价差多少、扣完美有没有利润」。",
          "Agent 会按你的场景（知道商品 / 知道品类 / 不知道卖什么）规划不同的探索策略。",
        ],
        links: [{ label: "开始选品演示", href: "/console/discovery/start/" }],
      },
      {
        id: "beginner",
        title: "我完全不知道卖什么，能用吗？",
        answer:
          "可以。开始选品支持「完全不知道卖什么」场景：描述你的约束（例如适合新手、期望利润门槛），Agent 会按利润、竞争、门槛等条件生成候选机会，你再挑品入库并持续监控。",
        paragraphs: [
          "新手不必先想好具体 SKU。选「不知道卖什么」，告诉 Agent 你的偏好和约束即可。",
          "系统会给出候选机会列表，附带利润率、竞争度与机会评分，帮你缩小第一批发力点。",
        ],
        links: [{ label: "三种选品场景", href: "/console/discovery/start/" }],
      },
      {
        id: "vs-manual",
        title: "和老卖家手动扒数据有什么区别？",
        answer:
          "老卖家往往靠经验加 Excel 手扒闲鱼和 1688。叮答把找热门、双边采集、同款配对、利润测算自动化，并把结果沉淀到商品库与监控里，减少重复劳动，让你把精力放在挑品和运营上。",
        paragraphs: [
          "手动流程：搜词 → 打开多个页面 → 复制价格 → 自己算利润 → 表格里难追踪后续变化。",
          "叮答：Agent 探索任务跑一遍，机会进商品库，监控帮你盯住后续价格波动。",
        ],
      },
      {
        id: "platforms",
        title: "支持哪些平台？",
        answer:
          "当前以闲鱼（需求端）和 1688（供货端）为主，覆盖跨平台倒货与无货源最常见的双边市场。小红书等渠道账号可在设置中管理，能力持续扩展中。",
        paragraphs: [
          "核心链路围绕闲鱼 × 1688 设计：一边看需求与成交价，一边看供货与采购价。",
          "其他渠道账号可在设置里预留，后续版本会逐步补齐采集能力。",
        ],
      },
      {
        id: "auto-sell",
        title: "叮答会自动帮我上架或发消息吗？",
        answer:
          "不会。叮答的定位是选品研究与决策辅助，不是自动运营机器人。Agent 只读查询本地数据并生成分析报告，上架、聊天、下单等操作仍需你在各平台自行完成。",
        paragraphs: [
          "我们刻意不做「全自动开店」，避免误操作和平台合规风险。",
          "叮答帮你更快找到有利润的货；卖不卖、怎么卖，决策权在你手里。",
        ],
      },
      {
        id: "open-source",
        title: "叮答开源吗？",
        answer:
          "是的。叮答在 GitHub 开源，欢迎查看源码、提 Issue 或参与贡献。技术栈为 Tauri + React + Rust，Agent 能力默认在 Rust 侧协调，仅在 Rust 生态不够时才使用 Python Sidecar。",
        paragraphs: [
          "代码公开可审计，本地数据存储方式透明。",
          "架构上 React 负责展示，Rust 负责协调与默认 AI 实现。",
        ],
        links: [{ label: "GitHub", href: "https://github.com/kingning2/dingda" }],
      },
    ],
  },
  {
    id: "start",
    label: "下载与入门",
    subtitle: "怎么装、怎么试、怎么发起第一次探索",
    seal: "门",
    items: [
      {
        id: "download",
        title: "如何下载和安装叮答？",
        answer:
          "在 GitHub Releases 页面下载对应系统的安装包（Windows / macOS / Linux）。安装后打开桌面端，按引导绑定闲鱼与 1688 账号，即可从工作台或选品发现进入第一次 Agent 探索。",
        paragraphs: [
          "第一步：在 Releases 下载与你系统匹配的安装包。",
          "第二步：安装并打开桌面端，完成账号绑定与基础设置。",
          "第三步：从「开始选品」或工作台发起第一次 Agent 比价探索任务。",
        ],
        links: [{ label: "前往 Releases", href: "https://github.com/kingning2/dingda/releases" }],
      },
      {
        id: "demo",
        title: "有免费演示吗？不用安装能看吗？",
        answer:
          "有。官网提供控制台演示，对齐桌面端工作台、选品发现、商品库、任务中心等界面，使用模拟数据展示流程。完整采集与比价需在桌面端连接真实账号后运行。",
        paragraphs: [
          "想先了解界面和流程，直接打开官网控制台演示即可，无需注册。",
          "演示数据为 mock；要跑真实 Agent 探索，请下载桌面端并绑定渠道账号。",
        ],
        links: [{ label: "打开控制台演示", href: "/console/" }],
      },
      {
        id: "first-run",
        title: "如何开始使用选品？",
        answer:
          "连接闲鱼与 1688 账号后，进入开始选品页，按你的情况选择三种场景之一：知道商品、知道品类、或完全不知道卖什么。填写关键词或描述后发起 Agent 探索，任务创建后可在任务中心查看进度与结果。",
        paragraphs: [
          "先确保渠道账号已连接，爬虫才能采到真实市场数据。",
          "选场景 → 填关键词或描述 → 发起探索 → 在任务中心看进度 → 有机会就入库。",
        ],
        links: [{ label: "开始选品演示", href: "/console/discovery/start/" }],
      },
      {
        id: "three-scenarios",
        title: "三种选品场景有什么区别？",
        answer:
          "知道商品：你已有具体品名，Agent 直接围绕该品做双边采集与利润分析。知道品类：你清楚大类但不确定具体 SKU，Agent 从品类扩展候选后再分析。完全不知道卖什么：你只描述约束与偏好，Agent 按利润、竞争、门槛推荐机会。",
        paragraphs: [
          "场景 A — 知道商品：例如「桌面风扇」，精准比对同款利润。",
          "场景 B — 知道品类：例如「宠物用品」，先扩展候选再筛选。",
          "场景 C — 不知道卖什么：例如「适合闲鱼新手的品」，由 Agent 推荐机会。",
        ],
      },
      {
        id: "tasks",
        title: "任务中心里的 Agent 任务是什么？",
        answer:
          "每次发起 Agent 探索（如 price_compare 比价探索）会在任务中心创建一条 AgentRun 任务，展示规划、采集、配对、分析各阶段状态。你可以追踪进度，完成后在选品发现或商品库查看结果。",
        paragraphs: [
          "任务中心是 Agent 探索的「飞行记录仪」——不是黑盒跑完就消失。",
          "常见任务类型包括比价探索；失败或卡住时可查看阶段日志排查。",
        ],
        links: [{ label: "任务中心演示", href: "/console/tasks/" }],
      },
      {
        id: "console-vs-desktop",
        title: "官网控制台和桌面端一样吗？",
        answer:
          "官网控制台是 Plan A 演示骨架：路由与桌面端 L1 导航 1:1 对齐，当前使用 mock 数据。桌面端是完整产品，连接真实账号、执行爬虫采集与 Agent 推理，数据写入本机 SQLite。",
        paragraphs: [
          "控制台：快速预览 UI 与信息架构，适合了解产品能做什么。",
          "桌面端：真实选品能力，适合日常找品、算利润、盯监控。",
        ],
        links: [{ label: "工作台演示", href: "/console/" }],
      },
      {
        id: "need-pc",
        title: "需要一直开着电脑吗？",
        answer:
          "Agent 探索与爬虫采集在桌面端运行时需保持应用开启。采集结果与商品库保存在本机，关闭后数据仍在。后续版本可能支持后台任务与定时探索，以桌面端实际能力为准。",
        paragraphs: [
          "探索任务执行期间请保持桌面端运行，以免采集中断。",
          "已入库的商品与历史结果会持久化在本地数据库，不依赖持续联网到叮答服务器。",
        ],
      },
      {
        id: "get-help",
        title: "遇到问题去哪求助？",
        answer:
          "可在 GitHub 仓库提 Issue 描述问题与复现步骤；也可查阅仓库文档与架构说明。官网 FAQ 与 llms.txt 提供产品与能力摘要，便于快速自助排查。",
        paragraphs: [
          "Bug 与功能建议：GitHub Issues。",
          "产品与能力概览：本页 FAQ 或 llms.txt。",
        ],
        links: [
          { label: "提 Issue", href: "https://github.com/kingning2/dingda/issues" },
          { label: "llms.txt", href: "/llms.txt" },
        ],
      },
    ],
  },
  {
    id: "account",
    label: "账号与设置",
    subtitle: "账号绑定、本地数据与 AI 配置",
    seal: "设",
    items: [
      {
        id: "which-accounts",
        title: "需要绑定哪些账号？",
        answer:
          "核心选品链路需要闲鱼（需求端）与 1688（供货端）账号，以便爬虫采集真实挂牌与成交参考。其他渠道账号可在设置中管理，按版本能力逐步开放。",
        paragraphs: [
          "闲鱼 + 1688 是当前比价探索的主链路，建议两个都绑定。",
          "账号信息用于渠道侧采集，存储在你本机，不上传叮答云端。",
        ],
        links: [{ label: "账号设置演示", href: "/console/settings/accounts/" }],
      },
      {
        id: "connect-accounts",
        title: "闲鱼 / 1688 账号怎么连接？",
        answer:
          "在桌面端设置 → 账号中按引导完成闲鱼与 1688 登录或授权。连接成功后，工作台会显示账号状态，即可发起 Agent 探索与爬虫采集。官网控制台仅为演示，不支持真实绑定。",
        paragraphs: [
          "桌面端：设置 → 账号 → 按渠道引导完成登录/授权。",
          "连接成功后，选品发现与任务中心才会使用真实数据（官网演示除外）。",
        ],
      },
      {
        id: "where-data",
        title: "数据存在哪里？",
        answer:
          "账号信息、采集结果、商品库、任务记录等默认存在本机 SQLite 数据库，由 Rust 基础设施层读写。你可备份数据目录；卸载前请自行导出需要保留的数据。",
        paragraphs: [
          "本地优先：你的选品数据跟着你的电脑走，不依赖叮答运营方的云端数据库。",
          "具体数据目录位置见桌面端文档或设置说明。",
        ],
      },
      {
        id: "agent-permissions",
        title: "Agent 能读写我的数据吗？",
        answer:
          "Agent 通过只读接口查询本机已采集的数据并生成分析结果，不会擅自修改商品库或发起渠道写操作。涉及上架、发消息等动作需你在各平台手动完成。",
        paragraphs: [
          "Agent 的角色是分析与建议，不是自动运营。",
          "敏感写操作不会由 Agent 静默执行。",
        ],
      },
      {
        id: "os-support",
        title: "支持哪些操作系统？",
        answer:
          "叮答桌面端基于 Tauri，支持 Windows、macOS 与 Linux。请从 GitHub Releases 选择对应平台的安装包。官网控制台为 Web 演示，任意现代浏览器均可访问。",
        paragraphs: [
          "桌面端：Windows / macOS / Linux。",
          "官网演示：Chrome、Edge、Safari 等现代浏览器。",
        ],
        links: [{ label: "下载", href: "https://github.com/kingning2/dingda/releases" }],
      },
      {
        id: "ai-config",
        title: "AI 模型怎么配置？",
        answer:
          "在桌面端设置 → AI 模型中配置推理后端与 API Key（若使用云端大模型）。Agent 规划与比价分析依赖模型能力；也可按版本支持接入本地模型。具体选项以桌面端设置页为准。",
        paragraphs: [
          "Agent 探索需要大模型参与规划与分析步骤。",
          "可在设置中选择模型提供商并填入密钥；本地模型支持取决于你的环境与版本。",
        ],
        links: [{ label: "AI 设置演示", href: "/console/settings/ai/" }],
      },
      {
        id: "profit-defaults",
        title: "利润测算的默认成本项在哪改？",
        answer:
          "在桌面端设置 → 利润默认中配置运费、包装、平台扣点等常用成本假设。利润计算器与机会列表会引用这些默认值，你也可以在单次测算时覆盖。",
        paragraphs: [
          "统一配置默认成本项，避免每个品都手填一遍。",
          "支持模板化成本结构，详见利润分析与成本模板模块。",
        ],
        links: [
          { label: "利润默认演示", href: "/console/settings/profit/" },
          { label: "成本模板", href: "/console/profit/templates/" },
        ],
      },
      {
        id: "reset-uninstall",
        title: "如何卸载或清空本地数据？",
        answer:
          "卸载桌面端应用后，本机 SQLite 数据文件可能仍保留在用户数据目录中，需手动删除以彻底清空。开源用户也可直接删除数据目录。卸载前请备份需要保留的商品库与任务记录。",
        paragraphs: [
          "卸载应用 ≠ 自动删除历史选品数据，请注意备份与手动清理。",
          "数据目录路径见项目文档；GitHub Issue 可咨询具体平台路径。",
        ],
      },
    ],
  },
];

/** 扁平列表 — 兼容 JSON-LD、首页摘要、llms.txt */
export const FAQS = FAQ_CATEGORIES.flatMap((category) =>
  category.items.map((item) => ({ q: item.title, a: item.answer })),
);

/** 首页展示的精选 FAQ */
export const HOME_FAQ_ITEMS: FaqItem[] = FAQ_CATEGORIES[0].items.slice(0, 6);
