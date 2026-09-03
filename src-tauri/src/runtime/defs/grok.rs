use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::empty_args;
use crate::runtime::model_discover::{discover_acp_models, static_models, AcpDiscoveryConfig};
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover(binary))
}

async fn discover(binary: &Path) -> Vec<RuntimeModel> {
    let models = discover_acp_models(
        binary,
        AcpDiscoveryConfig::with_args(&["--no-auto-update", "agent", "--always-approve", "stdio"]),
    )
    .await;
    if !models.is_empty() {
        return models;
    }
    static_models(&[
        ("grok-4.6", "Grok 4.6"),
        ("grok-4.5", "Grok 4.5"),
        ("grok-composer-2.5-fast", "Grok Composer 2.5 Fast"),
    ])
}

pub const GROK: RuntimeDefinition = RuntimeDefinition {
    id: "grok-build",
    name: "Grok Build",
    description: "xAI coding CLI",
    binary: "grok",
    fallback_binaries: &[],
    path_env_var: "DINGDA_GROK_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::Plain,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: false,
        supports_images: false,
        prompt_via_stdin: false,
    },
    install_url: "https://x.ai/cli",
    docs_url: "https://x.ai/cli",
    external_mcp_injection: None,
    is_default: false,
    build_args: empty_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
