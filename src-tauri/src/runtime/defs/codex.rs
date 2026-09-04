use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::codex_build_args;
use crate::runtime::model_discover::{parse_codex_debug_models, run_command, static_models};
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover(binary))
}

async fn discover(binary: &Path) -> Vec<RuntimeModel> {
    if run_command(binary, &["login", "status"]).await.is_ok() {
        if let Ok(stdout) = run_command(binary, &["debug", "models"]).await {
            let parsed = parse_codex_debug_models(&stdout);
            if !parsed.is_empty() {
                return parsed;
            }
        }
    }
    static_models(&[
        ("gpt-5.5", "GPT-5.5"),
        ("gpt-5.4", "GPT-5.4"),
        ("gpt-5.4-mini", "GPT-5.4 mini"),
        ("gpt-5.3-codex", "GPT-5.3-Codex"),
        ("gpt-5.2", "GPT-5.2"),
        ("gpt-5.1", "GPT-5.1"),
        ("gpt-5", "GPT-5"),
        ("o3", "o3"),
        ("o4-mini", "o4-mini"),
    ])
}

pub const CODEX: RuntimeDefinition = RuntimeDefinition {
    id: "codex",
    name: "Codex",
    description: "OpenAI official CLI",
    binary: "codex",
    fallback_binaries: &[],
    path_env_var: "DINGDA_CODEX_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::JsonEventStream,
    capabilities: RuntimeCapabilities {
        login_capable: true,
        supports_resume: true,
        prompt_via_stdin: true,
    },
    install_url: "https://github.com/openai/codex",
    docs_url: "https://developers.openai.com/codex",
    external_mcp_injection: Some("codex-mcp"),
    is_default: true,
    build_args: codex_build_args,
    validate_executable: None,
    auth_probe_args: Some(&["login", "status"]),
    discover_models,
};
