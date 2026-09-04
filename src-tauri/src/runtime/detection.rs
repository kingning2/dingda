use std::path::Path;

use super::resolution::resolve_executable;
use super::types::{RuntimeDefinition, RuntimeDetection};

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

    let authenticated = if definition.capabilities.login_capable {
        probe_auth(&resolved.path, definition).await
    } else if let Some(args) = definition.auth_probe_args {
        let arg_refs: Vec<&str> = args.iter().copied().collect();
        Some(run_command(&resolved.path, &arg_refs).await.is_ok())
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

pub async fn probe_auth(binary: &Path, definition: &RuntimeDefinition) -> Option<bool> {
    if definition.id == "codex" {
        return Some(run_command(binary, &["login", "status"]).await.is_ok());
    }
    if let Some(args) = definition.auth_probe_args {
        let arg_refs: Vec<&str> = args.iter().copied().collect();
        return Some(run_command(binary, &arg_refs).await.is_ok());
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
