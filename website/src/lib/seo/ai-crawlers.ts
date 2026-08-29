/**
 * AI 爬虫与 GEO 平台配置 — robots / meta / GEO 文件单一真相源。
 */

export type AiPlatform = {
  id: string;
  name: string;
  /** robots.txt User-Agent */
  userAgents: readonly string[];
  /** 是否国内主战场 */
  primary?: boolean;
};

/** 支持的 AI 平台与对应爬虫 UA */
export const AI_PLATFORMS: readonly AiPlatform[] = [
  {
    id: "doubao",
    name: "豆包",
    userAgents: ["Bytespider", "ToutiaoBot"],
    primary: true,
  },
  {
    id: "wenxin",
    name: "文心一言",
    userAgents: ["Baiduspider"],
    primary: true,
  },
  {
    id: "chatgpt",
    name: "ChatGPT",
    userAgents: ["GPTBot", "ChatGPT-User", "OAI-SearchBot"],
  },
  {
    id: "claude",
    name: "Claude",
    userAgents: ["ClaudeBot", "Claude-Web", "anthropic-ai"],
  },
  {
    id: "perplexity",
    name: "Perplexity",
    userAgents: ["PerplexityBot"],
  },
  {
    id: "gemini",
    name: "Gemini",
    userAgents: ["Google-Extended", "GoogleOther"],
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    userAgents: ["DeepSeekBot"],
  },
  {
    id: "kimi",
    name: "Kimi",
    userAgents: ["Moonshot-Kimi-User", "MoonshotBot"],
  },
  {
    id: "tongyi",
    name: "通义千问",
    userAgents: ["AliBot", "AlibabaSecurityBot"],
  },
  {
    id: "sogou",
    name: "搜狗 / 腾讯混元生态",
    userAgents: ["Sogou web spider", "Sogou inst spider"],
  },
  {
    id: "meta",
    name: "Meta AI",
    userAgents: ["FacebookBot", "meta-externalagent"],
  },
  {
    id: "apple",
    name: "Apple Intelligence",
    userAgents: ["Applebot-Extended"],
  },
  {
    id: "copilot",
    name: "Microsoft Copilot",
    userAgents: ["Bingbot"],
  },
  {
    id: "commoncrawl",
    name: "Common Crawl（多模型训练数据源）",
    userAgents: ["CCBot"],
  },
  {
    id: "cohere",
    name: "Cohere",
    userAgents: ["cohere-ai"],
  },
] as const;

/** 去重后的全部 AI 爬虫 UA（用于 meta） */
export const AI_CRAWLER_USER_AGENTS = [
  ...new Set(AI_PLATFORMS.flatMap((p) => p.userAgents)),
] as const;

/** 主战场平台 ID（豆包优先，兼顾国内其他） */
export const GEO_PRIMARY_PLATFORMS = AI_PLATFORMS.filter((p) => p.primary).map((p) => p.id);

export const GEO_PLATFORM_IDS = AI_PLATFORMS.map((p) => p.id);

/** GEO 摘要静态文件（public/） */
export const GEO_FILES = {
  llms: "llms.txt",
  aiGeo: "ai-geo.txt",
  doubaoGeo: "doubao-geo.txt",
} as const;
