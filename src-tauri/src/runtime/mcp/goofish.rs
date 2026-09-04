//! 叮答爬虫 MCP（`dingda-mcp`）启动参数与各 CLI 注入载荷。

use std::fs;
use std::path::Path;

use serde_json::{json, Map, Value};

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

/// Claude / Cursor / Qwen 等共用的 stdio 条目：`{command,args,env}`。
pub fn stdio_mcp_entry() -> Option<Value> {
    let command = dingda_mcp_uv_command()?;
    let cmd = command
        .first()
        .cloned()
        .unwrap_or_else(|| "uv".into());
    let args: Vec<String> = command.into_iter().skip(1).collect();
    Some(json!({
        "command": cmd,
        "args": args,
        "env": { "PYTHONUTF8": "1" }
    }))
}

/// 合并写入 JSON 文件的 `mcpServers.<name>`，保留其它键与其它 servers。
pub fn merge_mcp_servers_file(
    path: &Path,
    server_name: &str,
    entry: Value,
) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("创建目录失败: {e}"))?;
    }

    let mut root = if path.is_file() {
        let raw = fs::read_to_string(path).map_err(|e| format!("读取 {} 失败: {e}", path.display()))?;
        serde_json::from_str::<Value>(&raw).unwrap_or_else(|_| json!({ "mcpServers": {} }))
    } else {
        json!({ "mcpServers": {} })
    };

    let servers = root
        .as_object_mut()
        .ok_or_else(|| format!("{} 根必须是对象", path.display()))?
        .entry("mcpServers")
        .or_insert_with(|| Value::Object(Map::new()));

    let map = servers
        .as_object_mut()
        .ok_or_else(|| "mcpServers 必须是对象".to_string())?;
    map.insert(server_name.to_string(), entry);

    let text = serde_json::to_string_pretty(&root)
        .map_err(|e| format!("序列化 {} 失败: {e}", path.display()))?;
    fs::write(path, text).map_err(|e| format!("写入 {} 失败: {e}", path.display()))?;
    Ok(())
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

/// OpenCode / MiMo 共用的 inline config JSON（`mcp` 键）。
///
/// 无 server 时返回 `None`，调用方不得写入空 `*_CONFIG_CONTENT`。
pub fn opencode_style_config_content() -> Option<String> {
    let command = dingda_mcp_uv_command()?;
    Some(
        json!({
            "mcp": {
                SERVER_NAME: {
                    "type": "local",
                    "command": command,
                    "enabled": true,
                    "environment": {
                        "PYTHONUTF8": "1"
                    }
                }
            }
        })
        .to_string(),
    )
}

/// ACP `session/new` 用的 stdio MCP 条目列表。
///
/// env 用 `[{name,value}]`（ACP 常见形态；与 open-design 默认一致）。
pub fn acp_mcp_servers() -> Vec<Value> {
    let Some(command) = dingda_mcp_uv_command() else {
        return Vec::new();
    };
    let cmd = command.first().cloned().unwrap_or_else(|| "uv".into());
    let args: Vec<String> = command.into_iter().skip(1).collect();
    vec![json!({
        "type": "stdio",
        "name": SERVER_NAME,
        "command": cmd,
        "args": args,
        "env": [{ "name": "PYTHONUTF8", "value": "1" }]
    })]
}
