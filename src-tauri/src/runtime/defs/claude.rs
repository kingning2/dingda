use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::claude_build_args;
use crate::runtime::model_discover::static_models;
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    let _ = binary;
    Box::pin(async {
        static_models(&[
            ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
            ("claude-opus-4-6", "Claude Opus 4.6"),
            ("claude-sonnet-4-5", "Claude Sonnet 4.5"),
            ("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
            ("claude-opus-4-5", "Claude Opus 4.5"),
        ])
    })
}

pub const CLAUDE: RuntimeDefinition = RuntimeDefinition {
    id: "claude",
    name: "Claude",
    description: "Anthropic official CLI",
    binary: "claude",
    fallback_binaries: &[],
    path_env_var: "DINGDA_CLAUDE_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::ClaudeStreamJson,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: true,
        prompt_via_stdin: true,
    },
    install_url: "https://docs.anthropic.com/en/docs/claude-code/setup",
    docs_url: "https://docs.anthropic.com/en/docs/claude-code",
    external_mcp_injection: Some("claude-mcp-json"),
    is_default: false,
    build_args: claude_build_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
