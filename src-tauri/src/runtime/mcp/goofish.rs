//! 闲鱼 goofish MCP（`dingda-mcp`）启动参数。

use crate::paths::resolve_server_dir;

pub const SERVER_NAME: &str = "goofish";

/// `uv run --directory <server> dingda-mcp` 参数列表。
pub fn dingda_mcp_uv_command() -> Option<Vec<String>> {
    let server_dir = resolve_server_dir();
    if !server_dir.is_dir() {
        eprintln!(
            "[runtime/mcp] 跳过 goofish MCP：server 目录不存在 {}",
            server_dir.display()
        );
        return None;
    }

    let server = server_dir.to_string_lossy().replace('\\', "/");
    Some(vec![
        "uv".into(),
        "run".into(),
        "--directory".into(),
        server,
        "dingda-mcp".into(),
    ])
}

/// Codex `-c` 覆盖用的 TOML 片段。
pub fn codex_mcp_override() -> Option<String> {
    let command = dingda_mcp_uv_command()?;
    let server = command
        .iter()
        .skip_while(|part| *part != "--directory")
        .nth(1)?;
    Some(format!(
        r#"mcp_servers.{SERVER_NAME}={{"command"="uv","args"=["run","--directory","{server}","dingda-mcp"]}}"#
    ))
}
