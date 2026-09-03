//! 闲鱼 goofish MCP（`dingda-mcp`）启动参数。

use crate::paths::resolve_backend_dir;

pub const SERVER_NAME: &str = "goofish";

/// `uv run --directory <backend> dingda-mcp` 参数列表。
pub fn dingda_mcp_uv_command() -> Option<Vec<String>> {
    let backend_dir = resolve_backend_dir();
    if !backend_dir.is_dir() {
        eprintln!(
            "[runtime/mcp] 跳过 goofish MCP：backend 目录不存在 {}",
            backend_dir.display()
        );
        return None;
    }

    let backend = backend_dir.to_string_lossy().replace('\\', "/");
    Some(vec![
        "uv".into(),
        "run".into(),
        "--directory".into(),
        backend,
        "dingda-mcp".into(),
    ])
}

/// Codex `-c` 覆盖用的 TOML 片段。
pub fn codex_mcp_override() -> Option<String> {
    let command = dingda_mcp_uv_command()?;
    let backend = command
        .iter()
        .skip_while(|part| *part != "--directory")
        .nth(1)?;
    Some(format!(
        r#"mcp_servers.{SERVER_NAME}={{"command"="uv","args"=["run","--directory","{backend}","dingda-mcp"]}}"#
    ))
}
