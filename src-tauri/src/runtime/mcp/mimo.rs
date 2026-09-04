//! MiMo 运行时 MCP 注入：`MIMOCODE_CONFIG_CONTENT` 内联 JSON（与 OpenCode 同形）。

use crate::runtime::types::RuntimeInvocation;

use super::goofish;

/// 为一次 `mimo run` 注入 goofish MCP。
///
/// server 目录不存在时不设 `MIMOCODE_CONFIG_CONTENT`，避免空对象盖掉用户全局配置。
pub fn apply(invocation: &mut RuntimeInvocation) -> Result<(), String> {
    let Some(content) = goofish::opencode_style_config_content() else {
        return Ok(());
    };

    // 与 open-design 一致：进程级覆盖，不读项目 mimocode.json 里的冲突项
    invocation
        .env
        .entry("MIMOCODE_DISABLE_PROJECT_CONFIG".into())
        .or_insert_with(|| "true".into());
    invocation
        .env
        .insert("MIMOCODE_CONFIG_CONTENT".into(), content);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::path::PathBuf;

    #[test]
    fn injects_mimocode_config_content_env() {
        let mut invocation = RuntimeInvocation {
            runtime_id: "mimo".into(),
            executable: PathBuf::from("mimo"),
            args: vec!["run".into(), "--format".into(), "json".into()],
            cwd: PathBuf::from("."),
            env: HashMap::new(),
            prompt_via_stdin: true,
            prompt: Some("hi".into()),
            acp_mcp_servers: None,
        };

        apply(&mut invocation).expect("apply");

        let raw = invocation
            .env
            .get("MIMOCODE_CONFIG_CONTENT")
            .expect("MIMOCODE_CONFIG_CONTENT");
        assert!(raw.contains("\"goofish\""));
        assert!(raw.contains("dingda-mcp"));
        assert_eq!(
            invocation.env.get("MIMOCODE_DISABLE_PROJECT_CONFIG"),
            Some(&"true".into())
        );
    }
}
