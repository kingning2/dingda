//! 外部 Agent MCP 注入（按 `RuntimeDefinition.external_mcp_injection` 分发）。

mod codex;
mod goofish;
mod opencode;

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
        other => {
            eprintln!("[runtime/mcp] 未实现的 MCP 注入模式: {other}");
            Ok(())
        }
    }
}
