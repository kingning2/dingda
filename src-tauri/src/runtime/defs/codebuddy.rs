use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::empty_args;
use crate::runtime::model_discover::{
    discover_acp_models, static_models, AcpDiscoveryConfig,
};
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover(binary))
}

async fn discover(binary: &Path) -> Vec<RuntimeModel> {
    let models = discover_acp_models(binary, AcpDiscoveryConfig::with_args(&["--acp"])).await;
    if !models.is_empty() {
        return models;
    }
    static_models(&[
        ("claude-sonnet-4.6", "Claude Sonnet 4.6"),
        ("claude-opus-4.7", "Claude Opus 4.7"),
        ("gemini-3.1-pro", "Gemini 3.1 Pro"),
        ("gpt-5.5", "GPT 5.5"),
        ("deepseek-v3-2-volc-ioa", "Deepseek V3 2 Volc IOA"),
    ])
}

pub const CODEBUDDY: RuntimeDefinition = RuntimeDefinition {
    id: "codebuddy",
    name: "CodeBuddy",
    description: "Tencent CodeBuddy CLI",
    binary: "codebuddy",
    fallback_binaries: &[],
    path_env_var: "DINGDA_CODEBUDDY_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::ClaudeStreamJson,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: false,
        prompt_via_stdin: true,
    },
    install_url: "https://www.codebuddy.cn",
    docs_url: "https://www.codebuddy.cn/docs/workbuddy/Overview",
    external_mcp_injection: Some("claude-mcp-json"),
    is_default: false,
    build_args: empty_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
