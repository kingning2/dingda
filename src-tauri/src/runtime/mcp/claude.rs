//! Claude / CodeBuddy / Qoder / Grok：在 cwd 写入 `.mcp.json`（仅 dingda-mcp）。

use crate::runtime::types::RuntimeInvocation;

use super::goofish::{self, SERVER_NAME};

const MCP_JSON: &str = ".mcp.json";

/// 为一次会话合并写入 cwd 的 `.mcp.json`。
pub fn apply(invocation: &mut RuntimeInvocation) -> Result<(), String> {
    let Some(entry) = goofish::stdio_mcp_entry() else {
        return Ok(());
    };

    goofish::merge_mcp_servers_file(&invocation.cwd.join(MCP_JSON), SERVER_NAME, entry)?;
    invocation
        .env
        .entry("PYTHONUTF8".into())
        .or_insert_with(|| "1".into());
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::collections::HashMap;
    use std::fs;
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
            acp_mcp_servers: None,
        };

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

        goofish::merge_mcp_servers_file(
            &dir.join(MCP_JSON),
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
