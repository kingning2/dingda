//! 组装一次 CLI 启动：解析二进制、参数、prompt，并注入 MCP。

use std::collections::HashMap;
use std::path::PathBuf;

use super::mcp::apply_external_mcp_injection;
use super::prompts::compose_agent_prompt;
use super::resolution::resolve_executable;
use super::types::{RuntimeDefinition, RuntimeInvocation, RuntimeInvocationContext};

pub fn build_invocation(
    definition: &RuntimeDefinition,
    context: RuntimeInvocationContext,
    env: HashMap<String, String>,
) -> Result<RuntimeInvocation, String> {
    let resolved = resolve_executable(definition)
        .ok_or_else(|| format!("未找到可执行文件：{}", definition.binary))?;

    let args = (definition.build_args)(&context);
    let prompt = if definition.capabilities.prompt_via_stdin {
        Some(context.prompt)
    } else {
        None
    };

    let mut invocation = RuntimeInvocation {
        runtime_id: context.runtime_id,
        executable: resolved.path,
        args,
        cwd: context.cwd,
        env,
        prompt_via_stdin: definition.capabilities.prompt_via_stdin,
        prompt,
    };

    apply_external_mcp_injection(definition, &mut invocation)?;

    Ok(invocation)
}

/// 组装 invocation 上下文；`prompt` 在此统一拼上叮答系统前言（Markdown）。
pub fn invocation_context(
    definition: &RuntimeDefinition,
    prompt: String,
    cwd: PathBuf,
    model: Option<String>,
    session_id: Option<String>,
    reasoning: Option<String>,
    extra_allowed_dirs: Vec<PathBuf>,
) -> RuntimeInvocationContext {
    RuntimeInvocationContext {
        runtime_id: definition.id.to_string(),
        prompt: compose_agent_prompt(&prompt),
        cwd,
        model,
        session_id,
        reasoning,
        extra_allowed_dirs,
    }
}