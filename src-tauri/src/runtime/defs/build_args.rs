use super::super::types::RuntimeInvocationContext;

pub fn empty_args(_ctx: &RuntimeInvocationContext) -> Vec<String> {
    Vec::new()
}

pub fn version_only_args(_ctx: &RuntimeInvocationContext) -> Vec<String> {
    vec!["--version".to_string()]
}

pub fn codex_build_args(ctx: &RuntimeInvocationContext) -> Vec<String> {
    let mut args = vec![
        "exec".to_string(),
        "--json".to_string(),
        "--skip-git-repo-check".to_string(),
    ];
    if let Some(model) = &ctx.model {
        args.push("-m".to_string());
        args.push(model.clone());
    }
    args
}

pub fn claude_build_args(ctx: &RuntimeInvocationContext) -> Vec<String> {
    let mut args = vec![
        "-p".to_string(),
        "--input-format".to_string(),
        "stream-json".to_string(),
        "--output-format".to_string(),
        "stream-json".to_string(),
        "--verbose".to_string(),
    ];
    if let Some(model) = &ctx.model {
        args.push("--model".to_string());
        args.push(model.clone());
    }
    args
}

pub fn opencode_build_args(ctx: &RuntimeInvocationContext) -> Vec<String> {
    let mut args = vec!["run".to_string(), "--format".to_string(), "json".to_string()];
    if let Some(model) = &ctx.model {
        args.push("--model".to_string());
        args.push(model.clone());
    }
    args
}

pub fn cursor_build_args(ctx: &RuntimeInvocationContext) -> Vec<String> {
    let mut args = vec![
        "--print".to_string(),
        "--output-format".to_string(),
        "stream-json".to_string(),
        "--stream-partial-output".to_string(),
        "--force".to_string(),
    ];
    if let Some(model) = &ctx.model {
        args.push("--model".to_string());
        args.push(model.clone());
    }
    args
}

pub fn acp_serve_args(_ctx: &RuntimeInvocationContext) -> Vec<String> {
    vec!["acp".to_string()]
}

pub fn dsh_stdio_args(_ctx: &RuntimeInvocationContext) -> Vec<String> {
    vec!["--profile".to_string(), "multica".to_string(), "--stdio".to_string()]
}

pub fn plain_exec_args(ctx: &RuntimeInvocationContext) -> Vec<String> {
    vec!["exec".to_string(), "--auto".to_string(), ctx.prompt.clone()]
}
