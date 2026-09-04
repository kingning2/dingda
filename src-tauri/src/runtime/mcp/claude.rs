//! Claude / CodeBuddy：在 cwd 写入 `.mcp.json`（仅 dingda-mcp），不改用户 home。

use std::fs;
use std::path::Path;

use serde_json::{json, Map, Value};

use crate::runtime::types::RuntimeInvocation;

use super::goofish::{self, SERVER_NAME};

const MCP_JSON: &str = ".mcp.json";

/// 为一次 Claude 会话合并写入 cwd 的 `.mcp.json`。
pub fn apply(invocation: &mut RuntimeInvocation) -> Result<(), String> {
    let Some(command) = goofish::dingda_mcp_uv_command() else {
        return Ok(());
    };

    let (cmd, args) = split_command(&command);
    let entry = json!({
        "command": cmd,
        "args": args,
        "env": { "PYTHONUTF8": "1" }
    });

    write_mcp_json(&invocation.cwd, SERVER_NAME, entry)?;
    invocation
        .env
        .entry("PYTHONUTF8".into())
        .or_insert_with(|| "1".into());

    Ok(())
}

fn split_command(command: &[String]) -> (String, Vec<String>) {
    let cmd = command
        .first()
        .cloned()
        .unwrap_or_else(|| "uv".into());
    let args = command.iter().skip(1).cloned().collect();
    (cmd, args)
}

/// 合并写入 `.mcp.json`：只更新 dingda server 键，保留其它 mcpServers。
fn write_mcp_json(cwd: &Path, server_name: &str, entry: Value) -> Result<(), String> {
    fs::create_dir_all(cwd).map_err(|e| format!("创建 cwd 失败: {e}"))?;
    let path = cwd.join(MCP_JSON);

    let mut root = if path.is_file() {
        let raw = fs::read_to_string(&path).map_err(|e| format!("读取 .mcp.json 失败: {e}"))?;
        serde_json::from_str::<Value>(&raw).unwrap_or_else(|_| json!({ "mcpServers": {} }))
    } else {
        json!({ "mcpServers": {} })
    };

    let servers = root
        .as_object_mut()
        .ok_or_else(|| ".mcp.json 根必须是对象".to_string())?
        .entry("mcpServers")
        .or_insert_with(|| Value::Object(Map::new()));

    let map = servers
        .as_object_mut()
        .ok_or_else(|| "mcpServers 必须是对象".to_string())?;
    map.insert(server_name.to_string(), entry);

    let text = serde_json::to_string_pretty(&root)
        .map_err(|e| format!("序列化 .mcp.json 失败: {e}"))?;
    fs::write(&path, text).map_err(|e| format!("写入 .mcp.json 失败: {e}"))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::path::PathBuf;

    #[test]
    fn writes_goofish_into_mcp_json() {
        let dir = std::env::temp_dir().join(format!(
            "dingda-claude-mcp-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("mkdir");

        let mut invocation = RuntimeInvocation {
            runtime_id: "claude".into(),
            executable: PathBuf::from("claude"),
            args: vec!["-p".into()],
            cwd: dir.clone(),
            env: HashMap::new(),
            prompt_via_stdin: true,
            prompt: Some("hi".into()),
        };

        // server 目录若不存在则 skip；用假路径仍应能测 write 逻辑时
        // dingda_mcp_uv_command 依赖真实 server dir。有则写文件，无则 Ok 跳过。
        apply(&mut invocation).expect("apply");

        let path = dir.join(MCP_JSON);
        if path.is_file() {
            let raw = fs::read_to_string(&path).expect("read");
            assert!(raw.contains("goofish") || raw.contains("dingda-mcp") || raw.contains("uv"));
            assert_eq!(invocation.env.get("PYTHONUTF8"), Some(&"1".into()));
        }

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn merge_preserves_other_servers() {
        let dir = std::env::temp_dir().join(format!(
            "dingda-claude-mcp-merge-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("mkdir");
        fs::write(
            dir.join(MCP_JSON),
            r#"{"mcpServers":{"other":{"command":"echo"}}}"#,
        )
        .expect("seed");

        write_mcp_json(
            &dir,
            "goofish",
            json!({"command":"uv","args":["run","dingda-mcp"]}),
        )
        .expect("write");

        let raw = fs::read_to_string(dir.join(MCP_JSON)).expect("read");
        assert!(raw.contains("other"));
        assert!(raw.contains("goofish"));
        let _ = fs::remove_dir_all(&dir);
    }
}
