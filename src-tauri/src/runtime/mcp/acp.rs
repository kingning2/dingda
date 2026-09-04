//! ACP（Trae 等）：把 dingda-mcp 并进 `session/new` 的 `mcpServers`。
//!
//! 真正握手在 `process::spawn_process`：有 `acp_mcp_servers` 时走 initialize →
//! session/new → session/prompt，而不是把 prompt 当纯文本灌 stdin。

use crate::runtime::types::RuntimeInvocation;

use super::goofish;

/// 标记本次启动走 ACP merge；无 server 时仍设空数组，保证握手路径一致。
pub fn apply(invocation: &mut RuntimeInvocation) -> Result<(), String> {
    let servers = goofish::acp_mcp_servers();
    if servers.is_empty() {
        eprintln!("[runtime/mcp] acp-merge：无 dingda-mcp，仍走 ACP 握手（mcpServers=[]）");
    } else {
        eprintln!(
            "[runtime/mcp] acp-merge：注入 {} 个 stdio MCP",
            servers.len()
        );
    }
    invocation.acp_mcp_servers = Some(servers);
    // ACP 用 JSON-RPC 发 prompt，禁止再当纯文本 dump
    invocation.prompt_via_stdin = false;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::path::PathBuf;

    #[test]
    fn sets_acp_mcp_servers_and_disables_raw_stdin() {
        let mut invocation = RuntimeInvocation {
            runtime_id: "trae-cli".into(),
            executable: PathBuf::from("traecli"),
            args: vec!["acp".into()],
            cwd: PathBuf::from("."),
            env: HashMap::new(),
            prompt_via_stdin: true,
            prompt: Some("hi".into()),
            acp_mcp_servers: None,
        };

        apply(&mut invocation).expect("apply");

        assert!(invocation.acp_mcp_servers.is_some());
        assert!(!invocation.prompt_via_stdin);
        if let Some(servers) = &invocation.acp_mcp_servers {
            if !servers.is_empty() {
                let raw = servers[0].to_string();
                assert!(raw.contains("goofish") || raw.contains("dingda-mcp") || raw.contains("uv"));
            }
        }
    }
}
