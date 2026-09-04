//! 可执行文件二次校验：避免 PATH 撞名（如 Grok 的 `agent` 冒充 Cursor）。

use std::path::Path;
use std::process::Stdio;

/// DeepSeek Harness：`--probe` 必须回 dsh JSON。
pub fn validate_dsh_executable(executable: &Path) -> bool {
    let Ok(output) = std::process::Command::new(executable)
        .args(["--profile", "multica", "--probe"])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
    else {
        return false;
    };

    if !output.status.success() {
        return false;
    }

    for line in String::from_utf8_lossy(&output.stdout).lines() {
        let Ok(frame) = serde_json::from_str::<serde_json::Value>(line) else {
            continue;
        };
        if frame.get("v").and_then(|v| v.as_i64()) == Some(1)
            && frame.get("type").and_then(|v| v.as_str()) == Some("probe")
            && frame.get("runtime").and_then(|v| v.as_str()) == Some("dsh")
            && frame.get("protocol_version").and_then(|v| v.as_i64()) == Some(1)
        {
            return true;
        }
    }
    false
}

/// Cursor CLI：拒绝 Grok 等同名 `agent`；接受 `cursor-agent` 或路径/版本带 cursor 信号。
pub fn validate_cursor_executable(executable: &Path) -> bool {
    let Ok(output) = std::process::Command::new(executable)
        .args(["--version"])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
    else {
        return false;
    };

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let combined = format!("{stdout}\n{stderr}");
    looks_like_cursor_agent(executable, &combined)
}

/// 纯函数：路径 + `--version` 文本是否像 Cursor（供单测）。
pub fn looks_like_cursor_agent(executable: &Path, version_text: &str) -> bool {
    let path = executable.to_string_lossy().to_lowercase().replace('\\', "/");
    let version = version_text.to_lowercase();
    let stem = executable
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_lowercase();

    // Grok 安装目录 / 版本串直接否决
    if path.contains("/.grok/") || path.contains("/grok/") || version.contains("grok") {
        return false;
    }

    // 主命令名 unambiguous
    if stem == "cursor-agent" {
        return true;
    }

    // 备用名 `agent`：必须有 Cursor 安装路径或版本线索
    if stem == "agent" {
        return path.contains("cursor")
            || path.contains("/.local/bin/")
            || version.contains("cursor");
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn rejects_grok_agent_path() {
        let path = PathBuf::from(r"C:\Users\me\.grok\bin\agent.exe");
        assert!(!looks_like_cursor_agent(&path, "grok 1.0.5 (abc)"));
        assert!(!looks_like_cursor_agent(&path, "1.0.5"));
    }

    #[test]
    fn rejects_agent_with_grok_version() {
        let path = PathBuf::from(r"C:\Tools\agent.exe");
        assert!(!looks_like_cursor_agent(&path, "grok 1.0.5"));
    }

    #[test]
    fn accepts_cursor_agent_binary_name() {
        let path = PathBuf::from(r"C:\Tools\cursor-agent.exe");
        assert!(looks_like_cursor_agent(&path, "2025.1.0"));
    }

    #[test]
    fn accepts_agent_in_local_bin() {
        let path = PathBuf::from(r"C:\Users\me\.local\bin\agent.exe");
        assert!(looks_like_cursor_agent(&path, "2025.1.0"));
    }

    #[test]
    fn accepts_agent_with_cursor_in_version() {
        let path = PathBuf::from(r"C:\Tools\agent.exe");
        assert!(looks_like_cursor_agent(&path, "cursor-agent 1.2.3"));
    }

    #[test]
    fn rejects_bare_agent_without_cursor_signal() {
        let path = PathBuf::from(r"C:\Tools\agent.exe");
        assert!(!looks_like_cursor_agent(&path, "1.0.0"));
    }
}
