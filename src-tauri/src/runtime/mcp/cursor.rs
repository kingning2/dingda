//! Cursor Agent：在 cwd 写入 `.cursor/mcp.json`（项目级，不改 `~/.cursor`）。

use crate::runtime::types::RuntimeInvocation;

use super::goofish::{self, SERVER_NAME};

const MCP_JSON: &str = ".cursor/mcp.json";

/// 为一次 `cursor-agent` 会话合并写入项目 `.cursor/mcp.json`。
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
    use std::collections::HashMap;
    use std::fs;
    use std::path::PathBuf;

    #[test]
    fn writes_cursor_project_mcp_json() {
        let dir = std::env::temp_dir().join(format!(
            "dingda-cursor-mcp-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("mkdir");

        let mut invocation = RuntimeInvocation {
            runtime_id: "cursor-agent".into(),
            executable: PathBuf::from("cursor-agent"),
            args: vec!["--print".into()],
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
            assert!(raw.contains("goofish") || raw.contains("uv"));
        }
        let _ = fs::remove_dir_all(&dir);
    }
}
