//! OpenCode 运行时 MCP 注入：`OPENCODE_CONFIG_CONTENT` 内联 JSON，不改用户配置。

use serde_json::json;

use crate::runtime::types::RuntimeInvocation;

use super::goofish::{self, SERVER_NAME};

/// 为一次 `opencode run` 注入 goofish MCP。
pub fn apply(invocation: &mut RuntimeInvocation) -> Result<(), String> {
    let Some(command) = goofish::dingda_mcp_uv_command() else {
        return Ok(());
    };

    let content = json!({
        "$schema": "https://opencode.ai/config.json",
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
    });

    invocation.env.insert(
        "OPENCODE_CONFIG_CONTENT".into(),
        content.to_string(),
    );

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::path::PathBuf;

    #[test]
    fn injects_opencode_config_content_env() {
        let mut invocation = RuntimeInvocation {
            runtime_id: "opencode".into(),
            executable: PathBuf::from("opencode"),
            args: vec!["run".into(), "--format".into(), "json".into()],
            cwd: PathBuf::from("."),
            env: HashMap::new(),
            prompt_via_stdin: true,
            prompt: Some("hi".into()),
        };

        apply(&mut invocation).expect("apply");

        let raw = invocation
            .env
            .get("OPENCODE_CONFIG_CONTENT")
            .expect("OPENCODE_CONFIG_CONTENT");
        assert!(raw.contains("\"goofish\""));
        assert!(raw.contains("dingda-mcp"));
        assert!(raw.contains("\"type\":\"local\""));
    }
}
