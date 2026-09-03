use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::opencode_build_args;
use crate::runtime::model_discover::{parse_opencode_models, run_command};
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover(binary))
}

async fn discover(binary: &Path) -> Vec<RuntimeModel> {
    if let Ok(stdout) = run_command(binary, &["models", "--verbose"]).await {
        let parsed = parse_opencode_models(&stdout);
        if !parsed.is_empty() {
            return parsed;
        }
    }
    if let Ok(stdout) = run_command(binary, &["models"]).await {
        return parse_opencode_models(&stdout);
    }
    Vec::new()
}

pub const OPENCODE: RuntimeDefinition = RuntimeDefinition {
    id: "opencode",
    name: "OpenCode",
    description: "Open-source agent CLI",
    binary: "opencode",
    fallback_binaries: &["opencode-cli"],
    path_env_var: "DINGDA_OPENCODE_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::JsonEventStream,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: true,
        supports_images: false,
        prompt_via_stdin: true,
    },
    install_url: "https://opencode.ai/docs",
    docs_url: "https://github.com/sst/opencode",
    external_mcp_injection: Some("opencode-env-content"),
    is_default: false,
    build_args: opencode_build_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
