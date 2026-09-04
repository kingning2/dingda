//! Qwen Code：合并写入项目 `.qwen/settings.json` 的 `mcpServers`。

use serde_json::json;

use crate::runtime::types::RuntimeInvocation;

use super::goofish::{self, SERVER_NAME};

const SETTINGS_JSON: &str = ".qwen/settings.json";

/// 为一次 `qwen` 会话注入 goofish（`trust: true` 降低项目级审批摩擦）。
pub fn apply(invocation: &mut RuntimeInvocation) -> Result<(), String> {
    let Some(mut entry) = goofish::stdio_mcp_entry() else {
        return Ok(());
    };
    if let Some(obj) = entry.as_object_mut() {
        obj.insert("trust".into(), json!(true));
    }

    goofish::merge_mcp_servers_file(&invocation.cwd.join(SETTINGS_JSON), SERVER_NAME, entry)?;
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
    fn writes_qwen_settings_mcp() {
        let dir = std::env::temp_dir().join(format!(
            "dingda-qwen-mcp-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("mkdir");

        let mut invocation = RuntimeInvocation {
            runtime_id: "qwen".into(),
            executable: PathBuf::from("qwen"),
            args: vec![],
            cwd: dir.clone(),
            env: HashMap::new(),
            prompt_via_stdin: false,
            prompt: None,
            acp_mcp_servers: None,
        };

        apply(&mut invocation).expect("apply");

        let path = dir.join(SETTINGS_JSON);
        if path.is_file() {
            let raw = fs::read_to_string(&path).expect("read");
            assert!(raw.contains("goofish") || raw.contains("uv"));
            assert!(raw.contains("trust"));
        }
        let _ = fs::remove_dir_all(&dir);
    }
}
