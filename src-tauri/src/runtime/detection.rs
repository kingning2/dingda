use std::path::Path;

use super::resolution::resolve_executable;
use super::types::{AuthParse, RuntimeDefinition, RuntimeDetection};

pub async fn detect_runtime(definition: &RuntimeDefinition) -> RuntimeDetection {
    let Some(resolved) = resolve_executable(definition) else {
        return RuntimeDetection {
            available: false,
            executable: None,
            version: None,
            source: None,
            authenticated: None,
            error: Some(format!("未找到 {}", definition.binary)),
        };
    };

    let executable = resolved.path.display().to_string();
    let version = run_version_probe(&resolved.path, definition.version_args).await;

    // 有 version_args 却跑不通 → 当作未安装（避免 Windows 残留 .cmd 空壳被标成 available）
    if !definition.version_args.is_empty() && version.is_none() {
        return RuntimeDetection {
            available: false,
            executable: Some(executable),
            version: None,
            source: Some(resolved.source),
            authenticated: None,
            error: Some(format!("无法执行 {} --version", definition.binary)),
        };
    }

    let authenticated = if definition.auth.is_some() {
        probe_auth(&resolved.path, definition).await
    } else {
        None
    };

    RuntimeDetection {
        available: true,
        executable: Some(executable),
        version,
        source: Some(resolved.source),
        authenticated,
        error: None,
    }
}

/// 跑鉴权探针，按 `definition.auth.parse` 判定是否已登录。
///
/// 返回 `None` 表示「拿不到结论」（探针起不来，或输出不符合预期）——
/// 比误判成「未登录」安全。
pub async fn probe_auth(binary: &Path, definition: &RuntimeDefinition) -> Option<bool> {
    let auth = definition.auth?;
    let output = tokio::process::Command::new(binary)
        .args(auth.probe_args)
        .output()
        .await
        .ok()?;
    parse_auth_output(
        output.status.success(),
        &String::from_utf8_lossy(&output.stdout),
        auth.parse,
    )
}

/// 按 `parse` 判定探针输出。非零退出不一定等于未登录（见下方各分支）。
fn parse_auth_output(success: bool, stdout: &str, parse: AuthParse) -> Option<bool> {
    match parse {
        AuthParse::ExitCode => Some(success),
        // 非零退出说明命令本身没跑通，直接判未登录；否则以 JSON 为准。
        AuthParse::JsonLoggedIn => {
            if !success {
                return Some(false);
            }
            parse_json_logged_in(stdout)
        }
        AuthParse::CredentialCount => parse_credential_count(stdout),
    }
}

fn parse_json_logged_in(stdout: &str) -> Option<bool> {
    let value: serde_json::Value = serde_json::from_str(stdout.trim()).ok()?;
    value.get("loggedIn")?.as_bool()
}

/// 找形如 `1 credentials` 的计数；找不到返回 `None`（未知）。
fn parse_credential_count(stdout: &str) -> Option<bool> {
    for line in stdout.lines() {
        let Some(index) = line.find("credential") else {
            continue;
        };
        let Some(token) = line[..index].split_whitespace().last() else {
            continue;
        };
        if let Ok(count) = token.parse::<u64>() {
            return Some(count > 0);
        }
    }
    None
}

async fn run_version_probe(binary: &Path, version_args: &[&str]) -> Option<String> {
    if version_args.is_empty() {
        return None;
    }
    run_command(binary, version_args)
        .await
        .ok()
        .and_then(|out| first_line(&out))
}

async fn run_command(binary: &Path, args: &[&str]) -> Result<String, String> {
    let output = tokio::process::Command::new(binary)
        .args(args)
        .output()
        .await
        .map_err(|error| format!("无法执行 {}：{error}", binary.display()))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let detail = if !stderr.is_empty() {
            stderr
        } else if !stdout.is_empty() {
            stdout
        } else {
            format!("退出码 {}", output.status.code().unwrap_or(-1))
        };
        return Err(detail);
    }

    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn first_line(text: &str) -> Option<String> {
    text.lines()
        .map(str::trim)
        .find(|line| !line.is_empty())
        .map(str::to_string)
}

#[cfg(test)]
mod tests {
    use super::parse_auth_output;
    use crate::runtime::types::AuthParse;

    #[test]
    fn exit_code_uses_process_status() {
        assert_eq!(parse_auth_output(true, "", AuthParse::ExitCode), Some(true));
        assert_eq!(
            parse_auth_output(false, "not logged in", AuthParse::ExitCode),
            Some(false)
        );
    }

    #[test]
    fn json_logged_in_reads_claude_status() {
        assert_eq!(
            parse_auth_output(
                true,
                r#"{"loggedIn":true,"authMethod":"claude.ai"}"#,
                AuthParse::JsonLoggedIn
            ),
            Some(true)
        );
        assert_eq!(
            parse_auth_output(true, r#"{"loggedIn":false}"#, AuthParse::JsonLoggedIn),
            Some(false)
        );
    }

    #[test]
    fn json_logged_in_unknown_when_key_missing_or_not_bool() {
        assert_eq!(parse_auth_output(true, "{}", AuthParse::JsonLoggedIn), None);
        assert_eq!(
            parse_auth_output(true, r#"{"loggedIn":"yes"}"#, AuthParse::JsonLoggedIn),
            None
        );
        assert_eq!(
            parse_auth_output(true, "not json", AuthParse::JsonLoggedIn),
            None
        );
    }

    #[test]
    fn json_logged_in_treats_nonzero_exit_as_logged_out() {
        assert_eq!(
            parse_auth_output(false, "", AuthParse::JsonLoggedIn),
            Some(false)
        );
    }

    #[test]
    fn credential_count_parses_opencode_auth_list() {
        assert_eq!(
            parse_auth_output(true, "1 credentials\n", AuthParse::CredentialCount),
            Some(true)
        );
        assert_eq!(
            parse_auth_output(true, "0 credentials\n", AuthParse::CredentialCount),
            Some(false)
        );
    }

    #[test]
    fn credential_count_unknown_when_format_changes() {
        assert_eq!(
            parse_auth_output(true, "no stored auth\n", AuthParse::CredentialCount),
            None
        );
        assert_eq!(
            parse_auth_output(true, "", AuthParse::CredentialCount),
            None
        );
    }
}
