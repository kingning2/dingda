/**
 * Agent 执行引擎目录 — 与后端 `AGENT_REGISTRY` / `RUNTIME_REGISTRY` 对齐。
 */

export interface AgentCatalogEntry {
  id: string;
  name: string;
  description: string;
  install_url: string;
  docs_url: string;
  external_mcp_injection?: string | null;
}

/** 当前对外暴露的本地 Agent CLI（对齐 Rust RUNTIME_REGISTRY）。 */
export const AGENT_CATALOG: AgentCatalogEntry[] = [
  {
    id: "opencode",
    name: "OpenCode",
    description: "Open-source agent CLI",
    install_url: "https://opencode.ai/docs",
    docs_url: "https://github.com/sst/opencode",
    external_mcp_injection: "opencode-env-content",
  },
  {
    id: "claude",
    name: "Claude",
    description: "Anthropic official CLI",
    install_url: "https://docs.anthropic.com/en/docs/claude-code/setup",
    docs_url: "https://docs.anthropic.com/en/docs/claude-code",
    external_mcp_injection: "claude-mcp-json",
  },
  {
    id: "codex",
    name: "Codex",
    description: "OpenAI official CLI",
    install_url: "https://github.com/openai/codex",
    docs_url: "https://developers.openai.com/codex",
    external_mcp_injection: "codex-mcp",
  },
];
