/**
 * Agent 执行引擎目录 — 与后端 `AGENT_REGISTRY` 对齐。
 */

export interface AgentCatalogEntry {
  id: string;
  name: string;
  description: string;
  install_url: string;
  docs_url: string;
  external_mcp_injection?: string | null;
}

/** 当前支持的本地 Agent CLI（13 个）。 */
export const AGENT_CATALOG: AgentCatalogEntry[] = [
  {
    id: "claude",
    name: "Claude",
    description: "Anthropic official CLI",
    install_url: "https://docs.anthropic.com/en/docs/claude-code/setup",
    docs_url: "https://docs.anthropic.com/en/docs/claude-code",
    external_mcp_injection: "claude-mcp-json",
  },
  {
    id: "opencode",
    name: "OpenCode",
    description: "Open-source agent CLI",
    install_url: "https://opencode.ai/docs",
    docs_url: "https://github.com/sst/opencode",
    external_mcp_injection: "opencode-env-content",
  },
  {
    id: "mimo",
    name: "Mimo",
    description: "Mimo agent CLI",
    install_url: "https://mimo.ai",
    docs_url: "https://mimo.ai/docs",
    external_mcp_injection: "mimo-env-content",
  },
  {
    id: "codex",
    name: "Codex",
    description: "OpenAI official CLI",
    install_url: "https://github.com/openai/codex",
    docs_url: "https://developers.openai.com/codex",
    external_mcp_injection: "codex-mcp",
  },
  {
    id: "cursor-agent",
    name: "Cursor",
    description: "Cursor command line",
    install_url: "https://cursor.com/docs/cli/overview",
    docs_url: "https://docs.cursor.com/en/cli/overview",
  },
  {
    id: "deepseek-harness",
    name: "DeepSeek Harness",
    description: "DeepSeek native harness CLI",
    install_url: "https://www.deepseek.com/harness/en/",
    docs_url: "https://github.com/deepseek-ai/deepseek-harness",
  },
  {
    id: "qwen",
    name: "Qwen",
    description: "Qwen coding CLI",
    install_url: "https://github.com/QwenLM/qwen-code",
    docs_url: "https://qwenlm.github.io/qwen-code-docs/en/index",
  },
  {
    id: "qoder",
    name: "Qoder",
    description: "Alibaba coding CLI",
    install_url: "https://qoder.com/download",
    docs_url: "https://docs.qoder.com",
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    description: "DeepSeek terminal UI",
    install_url: "https://github.com/Hmbown/CodeWhale",
    docs_url: "https://github.com/Hmbown/CodeWhale/blob/main/README.md",
  },
  {
    id: "grok-build",
    name: "Grok Build",
    description: "xAI coding CLI",
    install_url: "https://x.ai/cli",
    docs_url: "https://x.ai/cli",
  },
  {
    id: "pi",
    name: "Pi",
    description: "Inflection chat CLI",
    install_url: "https://github.com/nexu-io/open-design/blob/main/docs/agent-adapters.md",
    docs_url: "https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md",
  },
  {
    id: "trae-cli",
    name: "Trae CLI",
    description: "ByteDance Trae agent CLI",
    install_url: "https://www.volcengine.com/docs/86677/2227861?lang=zh",
    docs_url: "https://www.volcengine.com/docs/86677/2227861?lang=zh",
    external_mcp_injection: "acp-merge",
  },
  {
    id: "codebuddy",
    name: "CodeBuddy",
    description: "Tencent CodeBuddy CLI",
    install_url: "https://www.codebuddy.cn",
    docs_url: "https://www.codebuddy.cn/docs/workbuddy/Overview",
    external_mcp_injection: "claude-mcp-json",
  },
];
