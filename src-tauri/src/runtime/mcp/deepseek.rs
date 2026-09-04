//! DeepSeek / CodeWhale：写进程级 mcp.json，经 `DEEPSEEK_MCP_CONFIG` 指向，不改 `~/.codewhale`。

use crate::runtime::types::RuntimeInvocation;

use super::goofish::{self, SERVER_NAME};

const MCP_REL: &str = ".dingda/mcp.json";

/// 写入 cwd 下 `.dingda/mcp.json`，并用环境变量覆盖 CodeWhale MCP 配置路径。
pub fn apply(invocation: &mut RuntimeInvocation) -> Result<(), String> {
    let Some(entry) = goofish::stdio_mcp_entry() else {
        return Ok(());
    };

    let path = invocation.cwd.join(MCP_REL);
    goofish::merge_mcp_servers_file(&path, SERVER_NAME, entry)?;

    let abs = path
        .canonicalize()
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/");

    invocation
        .env
        .insert("DEEPSEEK_MCP_CONFIG".into(), abs.clone());
    // 新版可能认 CODEWHALE_*；双写无害
    invocation
        .env
        .insert("CODEWHALE_MCP_CONFIG".into(), abs);
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
    fn sets_deepseek_mcp_config_env() {
        let dir = std::env::temp_dir().join(format!(
            "dingda-deepseek-mcp-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("mkdir");

        let mut invocation = RuntimeInvocation {
            runtime_id: "deepseek".into(),
            executable: PathBuf::from("codew"),
            args: vec!["exec".into()],
            cwd: dir.clone(),
            env: HashMap::new(),
            prompt_via_stdin: false,
            prompt: None,
            acp_mcp_servers: None,
        };

        apply(&mut invocation).expect("apply");

        if dir.join(MCP_REL).is_file() {
            let cfg = invocation
                .env
                .get("DEEPSEEK_MCP_CONFIG")
                .expect("DEEPSEEK_MCP_CONFIG");
            assert!(cfg.contains("mcp.json"));
            assert!(invocation.env.contains_key("CODEWHALE_MCP_CONFIG"));
        }
        let _ = fs::remove_dir_all(&dir);
    }
}
