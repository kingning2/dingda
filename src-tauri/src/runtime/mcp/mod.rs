//! 外部 Agent MCP 注入（按 `RuntimeDefinition.external_mcp_injection` 分发）。
//!
//! 仅注入内置 dingda-mcp（爬虫 search/product）；不写用户全局 CLI 配置。

mod acp;
mod claude;
mod codex;
mod cursor;
mod deepseek;
mod goofish;
mod mimo;
mod opencode;
mod pi;
mod qwen;

use crate::runtime::types::{RuntimeDefinition, RuntimeInvocation};

/// 在启动 CLI 前注入 MCP 配置（进程级，不写用户全局配置）。
pub fn apply_external_mcp_injection(
    definition: &RuntimeDefinition,
    invocation: &mut RuntimeInvocation,
) -> Result<(), String> {
    let Some(mode) = definition.external_mcp_injection else {
        return Ok(());
    };

    match mode {
        "codex-mcp" => codex::apply(invocation),
        "opencode-env-content" => opencode::apply(invocation),
        "mimo-env-content" => mimo::apply(invocation),
        "claude-mcp-json" => claude::apply(invocation),
        "cursor-mcp-json" => cursor::apply(invocation),
        "qwen-settings-json" => qwen::apply(invocation),
        "pi-mcp-json" => pi::apply(invocation),
        "deepseek-mcp-config" => deepseek::apply(invocation),
        "acp-merge" => acp::apply(invocation),
        other => {
            eprintln!("[runtime/mcp] 未实现的 MCP 注入模式: {other}");
            Ok(())
        }
    }
}
