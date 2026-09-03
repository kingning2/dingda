/**
 * MCP 接入契约 — 与 Python sidecar / 本地 daemon 响应对齐。
 * 前端只消费服务端返回的展示字段，不在组件内定义状态枚举。
 */

export type McpTransport = "stdio" | "sse" | "http";

/** 单条 MCP 服务运行态（由服务端探针组装）。 */
export interface McpServerStatusView {
  state: string;
  label: string;
  hint?: string | null;
  badge_class: string;
}

/** 已注册 MCP 服务（本地 daemon 或用户自定义）。 */
export interface McpServerItem {
  id: string;
  name: string;
  transport: McpTransport;
  /** stdio 启动命令（绝对路径或 PATH 内命令）。 */
  command?: string;
  args?: string[];
  /** sse / http 端点。 */
  url?: string;
  env?: Record<string, string>;
  enabled: boolean;
  /** builtin = 应用内置；user = 用户添加；preset = 模板导入。 */
  source: string;
  status: McpServerStatusView;
}

/** mcp_list 响应。 */
export interface McpListResponse {
  servers: McpServerItem[];
}
