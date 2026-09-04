/**

 * Agent 执行引擎契约 — 与 Python sidecar / 本地 daemon 响应对齐。

 * 叮答作为编排方拉起 Codex、Claude Code 等 CLI；前端只消费服务端探测结果。

 */



/** 单条 Agent CLI 运行态（由 daemon 探针组装）。 */

export interface AgentRuntimeStatusView {

  state: string;

  label: string;

  hint?: string | null;

  badge_class: string;

}



/** Agent CLI 鉴权状态（由本地 CLI 探针返回，如 `codex login status`）。 */

export interface AgentRuntimeAuthView {

  state: "authenticated" | "unauthenticated" | "unknown";

  label: string;

  /** 是否支持从平台触发 CLI 登录（如 `codex login`）。 */

  can_login?: boolean;

  hint?: string | null;

}



/** Agent 可用模型（由 CLI 动态发现，如 `codex debug models`）。 */

export interface AgentRuntimeModelView {

  id: string;

  label: string;

}



/** 本地可拉起的编码 Agent CLI（Codex / Claude Code / Cursor 等）。 */

export interface AgentRuntimeItem {

  id: string;

  name: string;

  description: string;

  /** daemon 是否在 PATH 中检测到可执行文件。 */

  available: boolean;

  version?: string | null;

  /** 探测到的可执行路径或命令名。 */

  command?: string | null;

  /** 可执行文件解析来源：configured | path | knownLocation */

  source?: string | null;

  /** 官方安装页（HTTPS）。 */

  install_url?: string | null;

  /** 配置与鉴权文档（HTTPS）。 */

  docs_url?: string | null;

  /** 是否为当前默认执行引擎。 */

  is_default?: boolean;

  /** 用户为该 Agent 持久化的默认模型 id（来自 SQLite）。 */

  preferred_model_id?: string | null;

  /**

   * 叮答向该 Agent 注入 MCP 的方式（由 daemon 定义，如 claude-mcp-json）。

   * null / 省略表示尚未接入原生注入。

   */

  external_mcp_injection?: string | null;

  /** CLI 鉴权状态；仅 available=true 且已探测时有值。 */

  auth?: AgentRuntimeAuthView | null;

  /** 当前账号可用模型；仅已登录且探测成功时有值。 */

  models?: AgentRuntimeModelView[] | null;

  /** 是否支持从平台触发 CLI 登录。 */

  can_login?: boolean;

  /** 是否支持本地探针。 */

  can_probe?: boolean;

  status: AgentRuntimeStatusView;

}



/** agent_list 响应。 */

export interface AgentListResponse {

  agents: AgentRuntimeItem[];

}



/** daemon / Tauri 探测原始响应（与 Rust `AgentRuntimeProbeResult` camelCase 对齐）。 */

export interface AgentRuntimeProbeResult {

  available: boolean;

  version?: string | null;

  command?: string | null;

  source?: string | null;

  authenticated?: boolean | null;

  models?: AgentRuntimeModelView[] | null;

  error?: string | null;

}



/** CLI 登录触发结果（如 `codex login`）。 */

export interface AgentRuntimeLoginResult {

  started: boolean;

  message: string;

}



/** Python `/v1/agent/default` 响应（SQLite 默认 Agent）。 */

export interface AgentDefaultView {

  ok?: boolean;

  default_agent_id: string | null;

}



/** Python `/v1/agent/preferences` 响应。 */

export interface AgentPreferencesView {

  ok?: boolean;

  default_agent_id: string | null;

  default_models: Record<string, string>;

}



/** Python `/v1/agent/default-model` 响应。 */

export interface AgentDefaultModelView {

  ok?: boolean;

  agent_id: string;

  model_id: string;

  default_models: Record<string, string>;

}



/** Python `/v1/agent/runtimes` 扫描目录缓存。 */

export interface AgentRuntimesCatalogView {

  ok?: boolean;

  agents: AgentRuntimeItem[];

}

