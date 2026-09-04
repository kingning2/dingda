//! 各 CLI 启动参数构建（对齐 open-design daemon 的 buildArgs 惯例）。

use std::path::PathBuf;

use super::super::types::RuntimeInvocationContext;

pub fn empty_args(_ctx: &RuntimeInvocationContext) -> Vec<String> {
    Vec::new()
}

/// Codex：`exec [--json] [--sandbox…]` 或 `exec resume [--json] [-c sandbox…] <thread_id>`。
/// prompt 走 stdin；Windows 默认 danger-full-access（与 open-design 一致）。
pub fn codex_build_args(ctx: &RuntimeInvocationContext) -> Vec<String> {
    let resume = ctx
        .session_id
        .as_ref()
        .map(|id| id.trim())
        .filter(|id| !id.is_empty());
    let danger = codex_needs_danger_full_access();

    let sandbox_args: Vec<String> = if danger {
        if resume.is_some() {
            vec!["-c".into(), "sandbox_mode=\"danger-full-access\"".into()]
        } else {
            vec!["--sandbox".into(), "danger-full-access".into()]
        }
    } else if resume.is_some() {
        vec![
            "-c".into(),
            "sandbox_mode=\"workspace-write\"".into(),
            "-c".into(),
            "sandbox_workspace_write.network_access=true".into(),
        ]
    } else {
        vec![
            "--sandbox".into(),
            "workspace-write".into(),
            "-c".into(),
            "sandbox_workspace_write.network_access=true".into(),
        ]
    };

    let mut args = if resume.is_some() {
        vec![
            "exec".into(),
            "resume".into(),
            "--json".into(),
            "--skip-git-repo-check".into(),
        ]
    } else {
        vec![
            "exec".into(),
            "--json".into(),
            "--skip-git-repo-check".into(),
        ]
    };
    args.extend(sandbox_args);

    // -C / --add-dir 仅新建会话可用；resume 会拒绝
    if resume.is_none() {
        let cwd = ctx.cwd.to_string_lossy();
        if !cwd.is_empty() {
            args.push("-C".into());
            args.push(cwd.into_owned());
        }
        for dir in &ctx.extra_allowed_dirs {
            let path = dir.to_string_lossy();
            if path.is_empty() {
                continue;
            }
            args.push("--add-dir".into());
            args.push(path.into_owned());
        }
    }

    if let Some(model) = ctx.model.as_ref().filter(|m| !m.is_empty() && m.as_str() != "default") {
        args.push("--model".into());
        args.push(model.clone());
    }
    if let Some(reasoning) = ctx
        .reasoning
        .as_ref()
        .filter(|r| !r.is_empty() && r.as_str() != "default")
    {
        args.push("-c".into());
        args.push(format!("model_reasoning_effort=\"{reasoning}\""));
    }

    // resume 的 thread id 必须在全部 flag 之后
    if let Some(session_id) = resume {
        args.push(session_id.to_string());
    }

    args
}

/// Claude Code：stream-json + 权限绕过 + 可选 resume / --add-dir。
pub fn claude_build_args(ctx: &RuntimeInvocationContext) -> Vec<String> {
    let mut args = vec![
        "-p".into(),
        "--input-format".into(),
        "stream-json".into(),
        "--output-format".into(),
        "stream-json".into(),
        "--verbose".into(),
    ];

    if let Some(session_id) = ctx.session_id.as_ref().filter(|id| !id.is_empty()) {
        args.push("--resume".into());
        args.push(session_id.clone());
    }
    if let Some(model) = ctx.model.as_ref().filter(|m| !m.is_empty() && m.as_str() != "default") {
        args.push("--model".into());
        args.push(model.clone());
    }

    append_add_dirs(&mut args, &ctx.extra_allowed_dirs);
    args.push("--permission-mode".into());
    args.push("bypassPermissions".into());
    args
}

/// OpenCode：`run --format json` + 权限绕过 + `--dir` + `-s` 续聊。
pub fn opencode_build_args(ctx: &RuntimeInvocationContext) -> Vec<String> {
    let mut args = vec!["run".into(), "--format".into(), "json".into()];
    // 与 open-design 一致：尽量绕过权限确认；旧版 CLI 若不识别会直接失败（更易排查）
    args.push("--dangerously-skip-permissions".into());

    let cwd = ctx.cwd.to_string_lossy();
    if !cwd.is_empty() {
        args.push("--dir".into());
        args.push(cwd.into_owned());
    }

    if let Some(session_id) = ctx.session_id.as_ref().filter(|id| !id.is_empty()) {
        args.push("-s".into());
        args.push(session_id.clone());
    }
    if let Some(model) = ctx.model.as_ref().filter(|m| !m.is_empty() && m.as_str() != "default") {
        args.push("-m".into());
        args.push(model.clone());
    }
    if let Some(variant) = ctx
        .reasoning
        .as_ref()
        .filter(|r| !r.is_empty() && r.as_str() != "default")
    {
        args.push("--variant".into());
        args.push(variant.clone());
    }
    args
}

/// Cursor Agent：非交互打印 + force。
pub fn cursor_build_args(ctx: &RuntimeInvocationContext) -> Vec<String> {
    let mut args = vec![
        "--print".into(),
        "--output-format".into(),
        "stream-json".into(),
        "--stream-partial-output".into(),
        "--force".into(),
    ];
    if let Some(model) = ctx.model.as_ref().filter(|m| !m.is_empty() && m.as_str() != "default") {
        args.push("--model".into());
        args.push(model.clone());
    }
    args
}

pub fn acp_serve_args(_ctx: &RuntimeInvocationContext) -> Vec<String> {
    vec!["acp".into()]
}

pub fn dsh_stdio_args(_ctx: &RuntimeInvocationContext) -> Vec<String> {
    vec![
        "--profile".into(),
        "multica".into(),
        "--stdio".into(),
    ]
}

pub fn plain_exec_args(ctx: &RuntimeInvocationContext) -> Vec<String> {
    let mut args = vec!["exec".into(), "--auto".into()];
    if let Some(model) = ctx.model.as_ref().filter(|m| !m.is_empty() && m.as_str() != "default") {
        args.push("--model".into());
        args.push(model.clone());
    }
    // 不支持 stdin 的 CLI 把 prompt 放在 argv 末尾
    if !ctx.prompt.is_empty() {
        args.push(ctx.prompt.clone());
    }
    args
}

fn append_add_dirs(args: &mut Vec<String>, dirs: &[PathBuf]) {
    let valid: Vec<String> = dirs
        .iter()
        .map(|d| d.to_string_lossy().into_owned())
        .filter(|p| !p.is_empty())
        .collect();
    if valid.is_empty() {
        return;
    }
    args.push("--add-dir".into());
    args.extend(valid);
}

fn codex_needs_danger_full_access() -> bool {
    if std::env::var("DINGDA_CODEX_SANDBOX")
        .map(|v| v.trim() == "danger-full-access")
        .unwrap_or(false)
    {
        return true;
    }
    // Windows / WSL：Codex workspace-write 会拦 shell，与 open-design 同策略
    if cfg!(windows) {
        return true;
    }
    std::env::var("WSL_DISTRO_NAME")
        .map(|v| !v.trim().is_empty())
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ctx(session_id: Option<&str>) -> RuntimeInvocationContext {
        RuntimeInvocationContext {
            runtime_id: "test".into(),
            prompt: "hi".into(),
            cwd: PathBuf::from("/tmp/proj"),
            model: Some("gpt-5".into()),
            session_id: session_id.map(str::to_string),
            reasoning: None,
            extra_allowed_dirs: vec![PathBuf::from("/tmp/extra")],
        }
    }

    #[test]
    fn opencode_appends_session_dir_and_permissions() {
        let args = opencode_build_args(&ctx(Some("ses_1")));
        assert!(args.windows(2).any(|w| w[0] == "-s" && w[1] == "ses_1"));
        assert!(args.windows(2).any(|w| w[0] == "--dir" && w[1] == "/tmp/proj"));
        assert!(args.iter().any(|a| a == "--dangerously-skip-permissions"));
        assert!(args.windows(2).any(|w| w[0] == "-m" && w[1] == "gpt-5"));
    }

    #[test]
    fn codex_resume_puts_session_id_last() {
        let args = codex_build_args(&ctx(Some("thread-1")));
        assert_eq!(args[0], "exec");
        assert_eq!(args[1], "resume");
        assert_eq!(args.last().map(String::as_str), Some("thread-1"));
        assert!(!args.iter().any(|a| a == "-C"));
        assert!(!args.iter().any(|a| a == "--add-dir"));
    }

    #[test]
    fn codex_create_includes_cwd_and_add_dir() {
        let args = codex_build_args(&ctx(None));
        assert!(args.windows(2).any(|w| w[0] == "-C" && w[1] == "/tmp/proj"));
        assert!(args.windows(2).any(|w| w[0] == "--add-dir" && w[1] == "/tmp/extra"));
        assert!(args.windows(2).any(|w| w[0] == "--model" && w[1] == "gpt-5"));
    }

    #[test]
    fn claude_appends_resume_permission_and_dirs() {
        let args = claude_build_args(&ctx(Some("uuid-1")));
        assert!(args.windows(2).any(|w| w[0] == "--resume" && w[1] == "uuid-1"));
        assert!(args.windows(2).any(|w| w[0] == "--permission-mode" && w[1] == "bypassPermissions"));
        assert!(args.iter().any(|a| a == "--add-dir"));
        assert!(args.iter().any(|a| a == "/tmp/extra"));
    }
}
