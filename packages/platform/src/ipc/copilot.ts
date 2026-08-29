/**
 * CopilotKit 副驾 IPC — 直连端点发现。
 *
 * 边界（CHG-20260829-007）：React 直连 Python 仅限副驾对话流（AG-UI SSE）；
 * 文件 / SQLite 等持久化一律由 Rust 处理。
 */

import { call } from "./invoke";

/** 副驾直连端点 URL；sidecar 未就绪或辅助 HTTP 未启动时为 null。 */
export function copilotEndpoint(): Promise<string | null> {
  return call<string | null>("copilot_endpoint");
}
