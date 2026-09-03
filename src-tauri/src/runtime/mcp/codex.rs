//! Codex 运行时 MCP 注入：通过 `codex -c` 覆盖，不修改 `~/.codex/config.toml`。

use crate::runtime::types::RuntimeInvocation;

use super::goofish;

/// 为一次 `codex exec` 注入 vendored `dingda-mcp`（闲鱼爬虫工具）。
pub fn apply(invocation: &mut RuntimeInvocation) -> Result<(), String> {
    let Some(config) = goofish::codex_mcp_override() else {
        return Ok(());
    };

    invocation.args.insert(0, config);
    invocation.args.insert(0, "-c".to_string());
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
    use std::path::PathBuf;

    #[test]
    fn injects_codex_config_override_before_exec() {
        let mut invocation = RuntimeInvocation {
            runtime_id: "codex".into(),
            executable: PathBuf::from("codex"),
            args: vec![
                "exec".into(),
                "--json".into(),
                "--skip-git-repo-check".into(),
            ],
            cwd: PathBuf::from("."),
            env: HashMap::new(),
            prompt_via_stdin: true,
            prompt: Some("hi".into()),
        };

        apply(&mut invocation).expect("apply");

        assert_eq!(invocation.args[0], "-c");
        assert!(invocation.args[1].contains("mcp_servers.goofish"));
        assert!(invocation.args[1].contains("dingda-mcp"));
        assert_eq!(invocation.args[2], "exec");
        assert_eq!(invocation.env.get("PYTHONUTF8"), Some(&"1".into()));
    }
}
